from django.urls import path

from categories.views import UserCategoryViewSet

urlpatterns = [
    path('categories/', UserCategoryViewSet.as_view(), name='user-categories'),
    path('categories/<uuid:id>/', UserCategoryViewSet.as_view(), name='user-category-detail'),
]