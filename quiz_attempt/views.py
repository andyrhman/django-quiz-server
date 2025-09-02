# attempts/views.py
from django.core.paginator import EmptyPage, Paginator
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

class AttemptReviewView(APIView):
    """
    GET /api/attempts/review/<uuid:attempt_id>/?question_page=1
    Returns:
      - attempt summary (score, percent, started_at, finished_at)
      - stats: total_questions, total_correct, total_incorrect
      - questions (1 per page) with options annotated: {is_correct, selected}
      - questions_meta for pagination (total, page, last_page)
    Access: attempt.user OR quiz owner OR admin-scope token
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id=None, *args, **kwargs):
        # 1) load attempt
        try:
            attempt = QuizAttempt.objects.select_related('quiz_info', 'user').get(id=attempt_id)
        except QuizAttempt.DoesNotExist:
            return Response({"detail": "QuizAttempt not found."}, status=status.HTTP_404_NOT_FOUND)

        # 2) permission check: attempt taker OR quiz owner OR admin
        quiz = attempt.quiz_info
        user = request.user
        if not (_is_admin_scope(request) or (user and user.is_authenticated and (attempt.user_id == user.id or (quiz.user_id and quiz.user_id == user.id)))):
            return Response({"detail": "You do not have permission to view this attempt review."}, status=status.HTTP_403_FORBIDDEN)
        
        quiz_info_data = {
            "id": str(quiz.id),
            "name": quiz.name,
            "time_limit": quiz.time_limit,
            "category": {
                "id": str(quiz.category.id) if quiz.category else None,
                "name": quiz.category.name if quiz.category else None
            },
            "user": {
                "id": str(quiz.user.id) if quiz.user else None,
                "username": quiz.user.username if quiz.user else None,
                # use attribute name you store on User model ('is_user' in your examples)
                "is_user": getattr(quiz.user, 'is_user', None) if quiz.user else None
            },
            "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
            "updated_at": quiz.updated_at.isoformat() if quiz.updated_at else None,
            "max_score": float(quiz.compute_max_score() or 0.0)
        }
        duration_seconds = None
        duration_human = None
        if attempt.started_at:
            end_time = attempt.finished_at if attempt.finished_at else timezone.now()
            # ensure timezone-aware arithmetic
            try:
                delta = end_time - attempt.started_at
                # total seconds (float) -> round/int as desired
                duration_seconds = int(delta.total_seconds())
                # format HH:MM:SS
                hrs, rem = divmod(duration_seconds, 3600)
                mins, secs = divmod(rem, 60)
                duration_human = f"{hrs:02d}:{mins:02d}:{secs:02d}"
            except Exception:
                # fallback in case of weird timezone types
                duration_seconds = None
                duration_human = None
        # 3) stats: total questions, total correct, total incorrect
        total_questions = quiz.quiz_info_questions.count()
        total_correct = attempt.attempt_answers.filter(is_correct=True).count()
        total_incorrect = attempt.attempt_answers.filter(is_correct=False).count()

        # 4) paginate questions: 1 per page
        question_page_num = int(request.query_params.get('question_page', 1))
        questions_qs = quiz.quiz_info_questions.all().order_by('question_no')
        paginator = Paginator(questions_qs, 1)

        try:
            page_obj = paginator.page(question_page_num)
            page_questions = list(page_obj.object_list)
        except EmptyPage:
            # out of range -> return empty question list but still include meta
            page_questions = []
            page_obj = None

        # decide whether to reveal explanation based on finished_at
        reveal_explanation = bool(attempt.finished_at)

        questions_payload = []
        for q in page_questions:
            # same submission resolution as above...
            try:
                submission = AnswerSubmission.objects.get(attempt=attempt, question=q)
                selected_set = set(str(x) for x in (submission.selected_option_ids or []))
                awarded_points = float(submission.awarded_points or 0.0)
                question_is_correct = bool(submission.is_correct)
            except AnswerSubmission.DoesNotExist:
                submission = None
                selected_set = set()
                awarded_points = 0.0
                question_is_correct = False

            opts = []
            for opt in q.quiz_question_options.all().order_by('order', 'created_at'):
                opt_id_str = str(opt.id)
                opts.append({
                    "id": str(opt.id),
                    "text": opt.text,
                    "order": opt.order,
                    "is_correct": bool(opt.is_correct),
                    "selected": opt_id_str in selected_set
                })

            questions_payload.append({
                "id": str(q.id),
                "question": q.question,
                "question_no": q.question_no,
                "question_type": q.question_type,
                "points": float(q.points),
                "awarded_points": awarded_points,
                "is_correct": question_is_correct,
                "explanation": q.explanation if reveal_explanation else None,
                "options": opts
            })

        # 6) assemble response
        questions_meta = {
            "total": paginator.count if paginator else 0,
            "page": question_page_num if paginator.count else 1,
            "last_page": paginator.num_pages if paginator else 1
        }

        attempt_summary = {
            "attempt_id": str(attempt.id),
            "user_id": str(attempt.user_id),
            "score": float(attempt.score),
            "percent_score": attempt.percent_score(),
            "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
            "finished_at": attempt.finished_at.isoformat() if attempt.finished_at else None,
            "duration_seconds": duration_seconds,
            "duration": duration_human
        }

        response = {
            "quiz_info": quiz_info_data,
            "attempt": attempt_summary,
            "stats": {
                "total_questions": total_questions,
                "total_correct": total_correct,
                "total_incorrect": total_incorrect
            },
            "questions_meta": questions_meta,
            "questions": questions_payload
        }

        return Response(response, status=status.HTTP_200_OK)