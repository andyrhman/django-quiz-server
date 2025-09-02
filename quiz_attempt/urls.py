from django.urls import path
from .views import AttemptReviewView, UserAttemptList, SubmitAnswersView, QuizInfoAttemptsList

urlpatterns = [
    path('attempts/', UserAttemptList.as_view(), name='user-attempt-list'),   # GET list of attempts for auth user
    path('attempts/submit/', SubmitAnswersView.as_view(), name='attempt-submit'),  # POST to submit answers
    path('quizinfo/<uuid:quiz_id>/attempts/', QuizInfoAttemptsList.as_view(), name='quizinfo-attempts'),  # admin/owner view
    path('attempts/review/<uuid:attempt_id>/', AttemptReviewView.as_view(), name='attempt-review'),
   
]
