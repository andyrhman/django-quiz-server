from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminDeleteQuizInfoView, QuizInfoViewSet

router = DefaultRouter()
router.register(r'quizinfo', QuizInfoViewSet, basename='admin-quizinfo')

urlpatterns = [
    path('', include(router.urls)),
    path('quizinfo-any/<uuid:id>/', AdminDeleteQuizInfoView.as_view(), name='admin-quizinfo-delete'),
]
