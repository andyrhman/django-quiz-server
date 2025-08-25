# quizzes/views.py
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializers import QuizInfoSerializer, QuizInfoSerializerCreateUpdate
from core.models import QuizInfo
from authorization.authentication import CookieJWTAuthentication
from authorization.permissions import ScopePermission

class QuizInfoViewSet(ModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    queryset = QuizInfo.objects.all()
    lookup_field = "id"
    
    def get_serializer_class(self):
        if self.request.method in 'POST':
            return QuizInfoSerializerCreateUpdate
        return QuizInfoSerializer
    
    def get_permissions(self):
        # public read access
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        # mutate actions require auth (and ScopePermission will still be enforced if present)
        return [IsAuthenticated(), ScopePermission()]
    
    def update(self, request, *args, **kwargs):
        quiz = self.get_object()
        
        token = getattr(request, 'auth', None)
        scope = token.get('scope') if hasattr(token, 'get') else None

        # Check if the user is allowed to update the quiz
        if scope == 'admin':
            # Admins can update any quiz
            return super().update(request, *args, **kwargs)
        elif scope == 'user':
            # Users can only update their own quizzes
            if quiz.user == request.user:
                return super().update(request, *args, **kwargs)
            else:
                return Response(
                    {"detail": "You do not have permission to update this quiz."},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )

    def partial_update(self, request, *args, **kwargs):
        quiz = self.get_object()
        
        token = getattr(request, 'auth', None)
        scope = token.get('scope') if hasattr(token, 'get') else None

        # Check if the user is allowed to partially update the quiz
        if scope == 'admin':
            # Admins can partially update any quiz
            resp = super().partial_update(request, *args, **kwargs)
            resp.status_code = status.HTTP_202_ACCEPTED
            return resp
        elif scope == 'user':
            # Users can only partially update their own quizzes
            if quiz.user == request.user:
                resp = super().partial_update(request, *args, **kwargs)
                resp.status_code = status.HTTP_202_ACCEPTED
                return resp
            else:
                return Response(
                    {"detail": "You do not have permission to update this quiz."},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
    
    def destroy(self, request, *args, **kwargs):
        quiz = self.get_object()
        
        token = getattr(request, 'auth', None)
        scope = token.get('scope') if hasattr(token, 'get') else None

        # Check if the user is allowed to delete the quiz
        if scope == 'admin':
            # Admins can delete any quiz
            return super().destroy(request, *args, **kwargs)
        elif scope == 'user':
            # Users can only delete their own quizzes
            if quiz.user == request.user:
                return super().destroy(request, *args, **kwargs)
            else:
                return Response(
                    {"detail": "You do not have permission to delete this quiz."},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
   
class AdminDeleteQuizInfoView(generics.DestroyAPIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    queryset = QuizInfo.objects.all()
    lookup_field = "id"