from rest_framework.viewsets import ModelViewSet
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import QuizQuestion, QuizOption
from .serializers import (
    QuizQuestionSerializer,
    QuizQuestionCreateUpdateSerializer,
    QuizOptionSerializer,
)
from authorization.authentication import CookieJWTAuthentication
from authorization.permissions import ScopePermission

def _token_scope(request):
    token = getattr(request, 'auth', None)
    return token.get('scope') if hasattr(token, 'get') else None

def _is_admin_scope(request):
    return _token_scope(request) == 'admin'

class QuizQuestionViewSet(ModelViewSet):
    """
    Manage questions.
    Only quiz owner or admin can create/update/delete questions for that quiz.
    Any authenticated user can list/retrieve public questions (or adjust as needed).
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    lookup_field = 'id'
    queryset = QuizQuestion.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return QuizQuestionCreateUpdateSerializer
        return QuizQuestionSerializer

    def update(self, request, *args, **kwargs):
        question = self.get_object()
        quiz = question.quiz_info

        if _is_admin_scope(request) or quiz.user == request.user:
            return super().update(request, *args, **kwargs)

        return Response(
            {"detail": "You do not have permission to update this question."},
            status=status.HTTP_403_FORBIDDEN
        )

    def partial_update(self, request, *args, **kwargs):
        question = self.get_object()
        quiz = question.quiz_info

        if _is_admin_scope(request) or quiz.user == request.user:
            resp = super().partial_update(request, *args, **kwargs)
            resp.status_code = status.HTTP_202_ACCEPTED
            return resp

        return Response(
            {"detail": "You do not have permission to update this question."},
            status=status.HTTP_403_FORBIDDEN
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        read_serializer = QuizQuestionSerializer(serializer.instance, context={'request': request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def handle_exception(self, exc):
        if isinstance(exc, PermissionError):
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().handle_exception(exc)
    
    def perform_create(self, serializer):
        # Ensure quiz exists & user is allowed to add question
        quiz = serializer.validated_data.get('quiz_info')
        # Admins can create for any quiz
        if _is_admin_scope(self.request):
            serializer.save()
            return

        # Regular user: allow only if they own the quiz
        if quiz.user == self.request.user:
            serializer.save()
            return

        # Not allowed
        raise PermissionError("You do not have permission to add questions to this quiz.")

    def destroy(self, request, *args, **kwargs):
        question = self.get_object()
        quiz = question.quiz_info

        if _is_admin_scope(request) or quiz.user == request.user:
            return super().destroy(request, *args, **kwargs)

        return Response(
            {"detail": "You do not have permission to delete this question."},
            status=status.HTTP_403_FORBIDDEN
        )

class QuizOptionViewSet(ModelViewSet):
    """
    Optional: manage options directly (edit single option).
    Ownership rules same as questions.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    serializer_class = QuizOptionSerializer
    queryset = QuizOption.objects.all()
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        option = self.get_object()
        quiz = option.question.quiz_info

        if _is_admin_scope(request) or quiz.user == request.user:
            return super().update(request, *args, **kwargs)

        return Response(
            {"detail": "You do not have permission to update this option."},
            status=status.HTTP_403_FORBIDDEN
        )

    def partial_update(self, request, *args, **kwargs):
        option = self.get_object()
        quiz = option.question.quiz_info

        if _is_admin_scope(request) or quiz.user == request.user:
            resp = super().partial_update(request, *args, **kwargs)
            resp.status_code = status.HTTP_202_ACCEPTED
            return resp

        return Response(
            {"detail": "You do not have permission to update this option."},
            status=status.HTTP_403_FORBIDDEN
        )

    def destroy(self, request, *args, **kwargs):
        opt = self.get_object()
        quiz = opt.question.quiz_info

        if _is_admin_scope(request) or quiz.user == request.user:
            return super().destroy(request, *args, **kwargs)

        return Response(
            {"detail": "You do not have permission to delete this option."},
            status=status.HTTP_403_FORBIDDEN
        )
