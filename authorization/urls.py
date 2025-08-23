from django.urls import path
from authorization.views import LoginAPIView, RegisterAPIView, TokenRefreshAPIView, LogoutAPIView, UserAPIView

urlpatterns = [
    path('auth/register/', RegisterAPIView.as_view(), name='login'),
    path('auth/login/', LoginAPIView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshAPIView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutAPIView.as_view(), name='logout'),
    path('me/', UserAPIView.as_view(), name='user-me'),
]
