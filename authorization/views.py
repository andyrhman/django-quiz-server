import uuid
import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status, exceptions
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken

from authorization.authentication import CookieJWTAuthentication
from authorization.redis_utils import create_session, get_session, revoke_session, update_session_jti
from authorization.utils import scope_from_path

from .permissions import ScopePermission
from .serializers import RegisterSerializer, UserSerializer  # assuming yours
from core.models import User  # adjust import path

class RegisterAPIView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        return Response(
            {"message": "Successfully Registered!"},
            status=status.HTTP_201_CREATED
        )

"""
A Short Explanation of the code:
- Why keep tokens in cookies? 
→ convenience for browser clients: cookies are automatically sent to your API on same-origin requests. If you set HttpOnly, JavaScript can’t read them (good for XSS protection).

- If the access token expires 
→ call the refresh endpoint to get a new access token (using the refresh token).

- If the refresh token expires or is invalid 
→ the user must log in again.

- Which token is the “real” sensitive one? 
→ the refresh token is more sensitive, because it can mint new access tokens. Protect it carefully. The access token is still sensitive (it grants access), but it’s short-lived so exposure risk is limited.
"""
COOKIE_SECURE = getattr(settings, 'JWT_COOKIE_SECURE', False)
COOKIE_SAMESITE = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
ACCESS_COOKIE_NAME = getattr(settings, 'JWT_COOKIE_NAME_ACCESS', 'access_token')
REFRESH_COOKIE_NAME = getattr(settings, 'JWT_COOKIE_NAME_REFRESH', 'refresh_token')

class LoginAPIView(APIView):
    def post(self, request):
        data = request.data
        user = None
        if "email" in data:
            try:
                user = User.objects.get(email=data["email"].lower())
            except ObjectDoesNotExist:
                return Response({"message": "Invalid email!"}, status=status.HTTP_400_BAD_REQUEST)
        elif "username" in data:
            try:
                user = User.objects.get(username=data["username"].lower())
            except ObjectDoesNotExist:
                return Response({"message": "Invalid username!"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"message": "Provide email or username."}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(data.get("password", "")):
            return Response({"message": "Invalid password"}, status=status.HTTP_400_BAD_REQUEST)

        if not getattr(user, 'is_verified', True):
            return Response({"message": "Please verify your account first"}, status=status.HTTP_403_FORBIDDEN)

        scope = "user" if "api/user" in request.path.lower() else "admin"
        if getattr(user, 'is_user', False) and scope == "admin":
            raise exceptions.AuthenticationFailed("Unauthorized")

        # Create refresh & access tokens
        refresh = RefreshToken.for_user(user)

        # Generate a stable session id (UUID) that will survive refresh rotations
        session_id = uuid.uuid4().hex

        session_jti = str(refresh['jti'])
        exp_ts = int(refresh['exp'])
        expires_at = datetime.datetime.fromtimestamp(exp_ts, tz=datetime.timezone.utc)

        # Save session mapping in redis: session_id -> { user_id, refresh_jti }
        create_session(session_id, str(user.id), session_jti, expires_at, scope)

        # Put session_id into tokens (access + refresh)
        refresh['session_id'] = session_id
        refresh['scope'] = scope

        access = refresh.access_token
        access['session_id'] = session_id
        access['scope'] = scope

        # Set cookies as before
        access_max_age = int((getattr(settings, 'SIMPLE_JWT', {}).get('ACCESS_TOKEN_LIFETIME', datetime.timedelta(minutes=15))).total_seconds())
        refresh_max_age = int((getattr(settings, 'SIMPLE_JWT', {}).get('REFRESH_TOKEN_LIFETIME', datetime.timedelta(days=1))).total_seconds())

        response = Response({"message": "Successfully logged in!"}, status=status.HTTP_200_OK)
        response.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=str(access),
            httponly=True,
            max_age=access_max_age,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            path='/'
        )
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=str(refresh),
            httponly=True,
            max_age=refresh_max_age,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            path='/'
        )
        return response


class TokenRefreshAPIView(APIView):
    """
    Rotate refresh tokens:
    - Client sends old refresh token (cookie).
    - Validate token, ensure session exists and that token.jti == session.refresh_jti.
    - If matches -> issue new refresh token + new access token, blacklist old refresh token, update redis mapping to new refresh_jti.
    - If mismatch -> revoke session (possible token replay) and deny.
    """
    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response({"message": "Refresh token not provided"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = RefreshToken(refresh_token)  # validates signature + expiry
        except Exception:
            return Response({"message": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        session_id = old_refresh.get('session_id')
        if not session_id:
            return Response({"message": "Malformed refresh token (no session)"},
                            status=status.HTTP_401_UNAUTHORIZED)
            
        requested_scope = scope_from_path(request.path)
        session = get_session(session_id)
        if not session:
            return Response({"message": "Session revoked or expired"}, status=status.HTTP_401_UNAUTHORIZED)
        if requested_scope and session.get('scope') != requested_scope:
            return Response({"message": "Invalid scope for this endpoint"}, status=status.HTTP_403_FORBIDDEN)
        
        session = get_session(session_id)
        if not session:
            # session missing -> revoked or expired
            return Response({"message": "Session revoked or expired"}, status=status.HTTP_401_UNAUTHORIZED)

        current_jti = session.get('refresh_jti')
        presented_jti = str(old_refresh.get('jti'))

        if presented_jti != current_jti:
            # token replay detected — revoke session for safety
            revoke_session(session_id)
            # optionally blacklist presented token (if blacklist configured)
            try:
                old_refresh.blacklist()
            except Exception:
                pass
            return Response({"message": "Refresh token reuse detected. Session revoked."}, status=status.HTTP_401_UNAUTHORIZED)

        # presented refresh jti matches current -> rotate
        user_id = session.get('user_id')
        # issue new refresh token
        new_refresh = RefreshToken.for_user_id(user_id) if hasattr(RefreshToken, 'for_user_id') else RefreshToken.for_user(User.objects.get(pk=user_id))
        # Add session_id & scope if needed
        new_refresh['session_id'] = session_id
        if 'scope' in old_refresh:
            new_refresh['scope'] = old_refresh['scope']

        new_jti = str(new_refresh.get('jti'))
        new_exp_ts = int(new_refresh.get('exp'))
        new_expires_at = datetime.datetime.fromtimestamp(new_exp_ts, tz=datetime.timezone.utc)

        # update redis mapping to point to new refresh jti and reset TTL
        update_session_jti(session_id, new_jti, new_expires_at)

        # blacklist the old refresh token to prevent reuse (requires token_blacklist app)
        try:
            old_refresh.blacklist()
        except Exception:
            pass

        # create new access token
        new_access = new_refresh.access_token
        new_access['session_id'] = session_id
        if 'scope' in new_refresh:
            new_access['scope'] = new_refresh['scope']

        access_max_age = int((getattr(settings, 'SIMPLE_JWT', {}).get('ACCESS_TOKEN_LIFETIME', datetime.timedelta(minutes=15))).total_seconds())
        refresh_max_age = int((getattr(settings, 'SIMPLE_JWT', {}).get('REFRESH_TOKEN_LIFETIME', datetime.timedelta(days=1))).total_seconds())

        response = Response({"message": "Token rotated"}, status=status.HTTP_200_OK)
        # set new cookies
        response.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=str(new_access),
            httponly=True,
            max_age=access_max_age,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            path='/'
        )
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=str(new_refresh),
            httponly=True,
            max_age=refresh_max_age,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            path='/'
        )
        return response
    
class UserAPIView(APIView):
    """
    Protected view — uses our cookie/header-aware authentication that also checks Redis session.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)

class LogoutAPIView(APIView):
    def post(self, request):
        # Prefer to revoke by refresh cookie (contains session_id)
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        session_id = None
        if refresh_token:
            try:
                rt = RefreshToken(refresh_token)
                session_id = rt.get('session_id')
                # note: don't blacklist here yet; we'll only blacklist if we actually revoke
            except Exception:
                pass

        # fallback: try to get session_id from access token in Authorization header or cookie
        if not session_id:
            auth_header = request.headers.get('Authorization', '')
            if auth_header and auth_header.lower().startswith('bearer '):
                raw = auth_header.split(' ', 1)[1].strip()
                try:
                    from rest_framework_simplejwt.tokens import UntypedToken
                    ut = UntypedToken(raw)
                    session_id = ut.get('session_id')
                except Exception:
                    pass
            else:
                # try cookie access token
                access_raw = request.COOKIES.get(ACCESS_COOKIE_NAME)
                if access_raw:
                    try:
                        from rest_framework_simplejwt.tokens import UntypedToken
                        ut = UntypedToken(access_raw)
                        session_id = ut.get('session_id')
                    except Exception:
                        pass

        # If we resolved a session_id, enforce that the session's scope matches the request scope
        if session_id:
            session = get_session(session_id)
            requested_scope = scope_from_path(request.path)

            if not session:
                # Already revoked/expired — still clear cookies for client
                response = Response({"message": "Session already revoked or expired"}, status=status.HTTP_200_OK)
                response.delete_cookie(ACCESS_COOKIE_NAME, path='/')
                response.delete_cookie(REFRESH_COOKIE_NAME, path='/')
                return response

            session_scope = session.get('scope')
            # if this logout endpoint is under /api/user/ we require session_scope == 'user', etc.
            if requested_scope and session_scope != requested_scope:
                # Deny: admin session trying to call user logout (or vice versa)
                return Response({"message": "Cannot logout session for a different scope."}, status=status.HTTP_403_FORBIDDEN)

            # session scope matches request scope -> revoke
            revoke_session(session_id)
            # blacklist refresh token if using token_blacklist (optional)
            try:
                if refresh_token:
                    rt.blacklist()
            except Exception:
                pass

        response = Response({"message": "Logged out"}, status=status.HTTP_200_OK)
        response.delete_cookie(ACCESS_COOKIE_NAME, path='/')
        response.delete_cookie(REFRESH_COOKIE_NAME, path='/')
        return response