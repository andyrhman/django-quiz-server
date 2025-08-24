# quizzes/views.py
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated

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
            
    def partial_update(self, request, *args, **kwargs):
        resp = super().partial_update(request, *args, **kwargs)
        resp.status_code = status.HTTP_202_ACCEPTED
        return resp
    
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

