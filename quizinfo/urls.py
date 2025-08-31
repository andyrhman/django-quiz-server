from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import QuizInfoDetailView, QuizInfoOwner, QuizInfoPreviewView, QuizInfoViewSet

router = DefaultRouter()
router.register(r'quizinfo', QuizInfoViewSet, basename='user-quizinfo')

urlpatterns = [
    path('', include(router.urls)),
    path('quizinfo/<uuid:id>/with-questions/', QuizInfoDetailView.as_view(), name='quizinfo-with-questions'),
    path('quizinfo/preview/<uuid:id>/with-questions-explanation/', QuizInfoPreviewView.as_view(), name='quizinfo-preview-with-questions-explanation'),
    path('quizinfos/owner/', QuizInfoOwner.as_view(), name='quizinfo-owner'),
]
