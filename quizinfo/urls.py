from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import QuizInfoViewSet

router = DefaultRouter()
router.register(r'quizinfo', QuizInfoViewSet, basename='user-quizinfo')

urlpatterns = [
    path('', include(router.urls)),
]
