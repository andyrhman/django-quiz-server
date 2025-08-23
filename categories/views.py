from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import generics, status

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
    
class UserCategoryViewSet(generics.ListAPIView, generics.RetrieveAPIView):
    permission_classes = [AllowAny]   
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    lookup_field = 'id'
    
    def get(self, request, *args, **kwargs):
        if 'id' in kwargs:
            return self.retrieve(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)