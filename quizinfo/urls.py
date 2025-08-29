from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import QuizInfoDetailView, QuizInfoOwner, QuizInfoViewSet

router = DefaultRouter()
router.register(r'quizinfo', QuizInfoViewSet, basename='user-quizinfo')

urlpatterns = [
    path('', include(router.urls)),
    path('quizinfo/<uuid:id>/with-questions/', QuizInfoDetailView.as_view(), name='quizinfo-with-questions'),
    path('quizinfos/owner/', QuizInfoOwner.as_view(), name='quizinfo-owner'),
]
