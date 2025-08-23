from rest_framework_simplejwt.authentication import JWTAuthentication as SimpleJWTAuth
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework import exceptions
from .redis_utils import get_session

class CookieJWTAuthentication(SimpleJWTAuth):
    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            raw_token = request.COOKIES.get(getattr(request, 'access_cookie_name', 'access_token')) or request.COOKIES.get('access_token')

        if not raw_token:
            return None

        try:
            validated_token = UntypedToken(raw_token)
        except Exception as e:
            raise exceptions.AuthenticationFailed('Invalid or expired token') from e

        session_id = validated_token.get('session_id')
        if not session_id:
            raise exceptions.AuthenticationFailed('Token missing session id')

        session = get_session(session_id)
        if not session:
            raise exceptions.AuthenticationFailed('Session revoked or expired')

        # optional: verify user_id matches token's user if you want extra safety
        user = self.get_user(validated_token)
        return (user, validated_token)
