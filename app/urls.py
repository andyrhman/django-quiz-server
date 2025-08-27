"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from rest_framework.documentation import include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/user/', include(('authorization.urls', 'user'), namespace='user_auth')),
    path('api/admin/', include(('authorization.urls', 'auth'), namespace='admin_auth')),
    path('api/admin/', include(('categories.urls_admin', 'categories'), namespace='admin_category')),
    path('api/admin/', include(('quizinfo.urls_admin', 'quizinfo'), namespace='admin_quizinfo')),
    path('api/admin/', include(('quiz_question_option.urls_admin', 'quiz_question_option'), namespace='admin_quiz_question_option')),
    path('api/', include(('categories.urls', 'categories'), namespace='user_category')),
    path('api/', include(('quizinfo.urls', 'quizinfo'), namespace='user_quizinfo')),
    path('api/', include(('quiz_question_option.urls', 'quiz_question_option'), namespace='user_quiz_question_option')),
    path('api/', include(('quiz_attempt.urls', 'quiz_attempt'), namespace='user_quiz_attempt')),
]