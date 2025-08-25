from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuizQuestionViewSet, QuizOptionViewSet

router = DefaultRouter()
router.register(r'questions', QuizQuestionViewSet, basename='user-question')
router.register(r'options', QuizOptionViewSet, basename='user-option')

urlpatterns = [
    path('', include(router.urls)),
]