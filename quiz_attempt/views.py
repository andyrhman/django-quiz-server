# attempts/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Prefetch

from core.models import QuizAttempt, QuizInfo, AnswerSubmission, QuizQuestion
from .serializers import QuizAttemptSerializer
from authorization.authentication import CookieJWTAuthentication

def _token_scope(request):
    token = getattr(request, 'auth', None)
    try:
        return token.get('scope') if token and hasattr(token, 'get') else getattr(token, 'scope', None)
    except Exception:
        return None

def _is_admin_scope(request):
    return _token_scope(request) == 'admin'


class UserAttemptList(generics.ListAPIView):
    """
    GET /api/attempts/
    List attempts that belong to the authenticated user.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = QuizAttemptSerializer

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user).select_related('quiz_info').prefetch_related('attempt_answers')


class QuizInfoAttemptsList(generics.ListAPIView):
    """
    GET /api/quizinfos/{quiz_id}/attempts/
    Returns all attempts for the given quiz (only admin or quiz owner).
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]  # further checked in get()
    serializer_class = QuizAttemptSerializer
    lookup_url_kwarg = 'quiz_id'

    def get(self, request, *args, **kwargs):
        quiz_id = kwargs.get(self.lookup_url_kwarg)
        try:
            quiz = QuizInfo.objects.get(id=quiz_id)
        except QuizInfo.DoesNotExist:
            return Response({"detail": "QuizInfo not found."}, status=status.HTTP_404_NOT_FOUND)

        # permission: admin scope OR quiz owner
        if not (_is_admin_scope(request) or (quiz.user and quiz.user == request.user)):
            return Response({"detail": "You do not have permission to view attempts for this quiz."},
                            status=status.HTTP_403_FORBIDDEN)

        # Good — return attempts
        qs = QuizAttempt.objects.filter(quiz_info=quiz).select_related('user').prefetch_related('attempt_answers')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubmitAnswersView(APIView):
    """
    POST /api/attempts/submit/
    Existing submit endpoint but ensure finished_at is set when 'finish' flag is true.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        payload = request.data
        quiz_id = payload.get('quiz_info')
        answers = payload.get('answers', [])
        attempt_id = payload.get('attempt_id')
        finish = bool(payload.get('finish', False))

        # validate quiz
        try:
            quiz = QuizInfo.objects.get(id=quiz_id)
        except QuizInfo.DoesNotExist:
            return Response({"detail": "quiz_info not found"}, status=status.HTTP_400_BAD_REQUEST)

        # get or create attempt
        if attempt_id:
            try:
                attempt = QuizAttempt.objects.get(id=attempt_id, user=user, quiz_info=quiz)
            except QuizAttempt.DoesNotExist:
                return Response({"detail": "attempt not found or does not belong to user"}, status=status.HTTP_400_BAD_REQUEST)
            # prevent re-submitting to a finished attempt unless you allow revisits
            if attempt.finished_at:
                # optional: allow update of answers but most systems prevent it
                # return Response({"detail":"Attempt already finished."}, status=status.HTTP_400_BAD_REQUEST)
                pass
        else:
            attempt = QuizAttempt.objects.create(user=user, quiz_info=quiz)

        created_submissions = []
        for ans in answers:
            qid = ans.get('question_id')
            selected = ans.get('selected_option_ids', [])
            if qid is None:
                continue

            try:
                question = QuizQuestion.objects.select_related('quiz_info').get(id=qid, quiz_info=quiz)
            except QuizQuestion.DoesNotExist:
                return Response({"detail": f"question {qid} not found in quiz"}, status=status.HTTP_400_BAD_REQUEST)

            selected_set = set(str(s) for s in (selected or []))
            correct_qs = question.quiz_question_options.filter(is_correct=True)
            correct_ids = set(str(x.id) for x in correct_qs)

            if question.question_type == 'single':
                is_correct = (len(selected_set) == 1 and next(iter(selected_set)) in correct_ids)
                awarded = float(question.points) if is_correct else 0.0
            else:
                if selected_set == correct_ids:
                    is_correct = True
                    awarded = float(question.points)
                else:
                    is_correct = False
                    if len(correct_ids) > 0:
                        correct_selected = len(selected_set & correct_ids)
                        awarded = (correct_selected / len(correct_ids)) * float(question.points)
                    else:
                        awarded = 0.0

            sub, created = AnswerSubmission.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={
                    'selected_option_ids': list(selected_set),
                    'is_correct': is_correct,
                    'awarded_points': awarded,
                    'answered_at': timezone.now()
                }
            )

            created_submissions.append({
                "question_id": str(question.id),
                "is_correct": is_correct,
                "awarded_points": awarded
            })

        # Recompute total score from DB (safe)
        agg = AnswerSubmission.objects.filter(attempt=attempt).aggregate(total=Sum('awarded_points'))
        attempt.score = float(agg['total'] or 0.0)

        # mark finished if requested — this is the fix you asked for
        if finish:
            attempt.finished_at = timezone.now()

        attempt.save()

        return Response({
            "attempt_id": str(attempt.id),
            "score": attempt.score,
            "percent_score": attempt.percent_score(),
            "finished_at": attempt.finished_at,
            "answers": created_submissions
        }, status=status.HTTP_200_OK)
