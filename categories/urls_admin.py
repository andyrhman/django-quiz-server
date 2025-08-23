from django.urls import path, include
from rest_framework.routers import DefaultRouter
from categories.views import AdminCategoryViewSet

router = DefaultRouter()
router.register(r'categories', AdminCategoryViewSet, basename='admin-category')

urlpatterns = [
    path('', include(router.urls)),
]