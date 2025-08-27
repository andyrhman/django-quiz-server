from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .pagination import QuizInfoListPagination
from .serializers import QuizInfoDetailSerializer, QuizInfoSerializer, QuizInfoSerializerCreateUpdate, QuizOptionNestedSerializer, QuizQuestionNestedSerializer
from core.models import QuizInfo
from authorization.authentication import CookieJWTAuthentication
from authorization.permissions import ScopePermission

class QuizInfoViewSet(ModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    queryset = QuizInfo.objects.all()
    lookup_field = "id"
    pagination_class = QuizInfoListPagination

    def get_serializer_class(self):
        # fixed check: equality, not 'in' string
        if self.request.method == 'POST':
            return QuizInfoSerializerCreateUpdate
        return QuizInfoSerializer

    def get_queryset(self):
        """
        Support filtering by category name(s) via ?categories=Name or ?categories=Name1,Name2
        Case-insensitive match against category.name.
        """
        qs = QuizInfo.objects.all().select_related('category', 'user')
        categories = self.request.query_params.get('categories')
        if categories:
            names = [c.strip() for c in categories.split(',') if c.strip()]
            if names:
                q = Q()
                for name in names:
                    q |= Q(category__name__iexact=name)
                qs = qs.filter(q)
        return qs
    
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
            
class QuizInfoDetailView(generics.RetrieveAPIView):
    """
    GET /api/quizinfos/<id>/with-questions/?question_page=1&option_page=1&option_page_size=5
    Returns quiz info + exactly 1 question (question_page) and paginated options (option_page).
    """
    permission_classes = [AllowAny]
    lookup_field = 'id'
    serializer_class = QuizInfoDetailSerializer  # not used to render nested page, but keep for compatibility
    queryset = QuizInfo.objects.all().select_related('category', 'user').prefetch_related(
        'quiz_info_questions__quiz_question_options'
    )

    def get(self, request, *args, **kwargs):
        quiz = self.get_object()

        # paginate questions: 1 per page
        questions_qs = quiz.quiz_info_questions.all().order_by('question_no')
        question_page_num = int(request.query_params.get('question_page', 1))
        question_paginator = Paginator(questions_qs, 1)
        try:
            question_page = question_paginator.page(question_page_num)
        except EmptyPage:
            # return empty questions list with meta if page out of range
            base_data = QuizInfoSerializer(quiz, context={'request': request}).data
            base_data['questions'] = []
            base_data['questions_meta'] = {
                "total": question_paginator.count,
                "page": question_page_num if question_paginator.count else 1,
                "last_page": question_paginator.num_pages
            }
            return Response(base_data)

        # get the single question object (or none)
        q_obj = question_page.object_list[0] if question_page.object_list else None

        # serialize quiz base info (without embedding all questions)
        base_data = QuizInfoSerializer(quiz, context={'request': request}).data

        # if no question present, respond accordingly
        if q_obj is None:
            base_data['questions'] = []
            base_data['questions_meta'] = {
                "total": question_paginator.count,
                "page": question_page_num if question_paginator.count else 1,
                "last_page": question_paginator.num_pages
            }
            return Response(base_data)

        # serialize the question (basic fields)
        q_ser = QuizQuestionNestedSerializer(q_obj, context={'request': request})
        q_data = q_ser.data  # contains options (full) — we will replace with paginated options

        # paginate options for this question
        option_page_num = int(request.query_params.get('option_page', 1))
        option_page_size = int(request.query_params.get('option_page_size', 5))
        options_qs = q_obj.quiz_question_options.all().order_by('order', 'created_at')
        option_paginator = Paginator(options_qs, option_page_size)

        try:
            option_page = option_paginator.page(option_page_num)
            option_objs = option_page.object_list
        except EmptyPage:
            option_objs = []
            option_page_num = option_paginator.num_pages or 1

        # serialize only the paginated options
        option_ser = QuizOptionNestedSerializer(option_objs, many=True, context={'request': request})
        options_data = option_ser.data

        # attach paginated options and meta to question data
        q_data['options'] = options_data
        q_data['options_meta'] = {
            "total": option_paginator.count,
            "page": option_page_num if option_paginator.count else 1,
            "last_page": option_paginator.num_pages
        }

        # attach questions array (single item) and meta to base_data
        base_data['questions'] = [q_data]
        base_data['questions_meta'] = {
            "total": question_paginator.count,
            "page": question_page_num if question_paginator.count else 1,
            "last_page": question_paginator.num_pages
        }

        return Response(base_data)
    
class AdminDeleteQuizInfoView(generics.DestroyAPIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    queryset = QuizInfo.objects.all()
    lookup_field = "id"