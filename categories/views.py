from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status
from rest_framework.response import Response

from authorization.authentication import CookieJWTAuthentication
from authorization.permissions import ScopePermission
from core.models import Category
from .serializers import CategorySerializer

class AdminCategoryViewSet(ModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopePermission]
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    lookup_field = 'id'

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        response.status_code = status.HTTP_202_ACCEPTED
        return response