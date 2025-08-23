import time
import uuid
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None):
        if not email:
            raise ValueError("User must have an email")
        if not username:
            raise ValueError("User must have a username")
        if not password:
            raise ValueError("User must have a password")

        user = self.model(email=self.normalize_email(email), username=username)
        user.set_password(password)
        user.is_admin = False
        user.is_staff = False
        user.is_ambassador = False
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None):
        if not email:
            raise ValueError("User must have an email")
        if not username:
            raise ValueError("User must have a username")
        if not password:
            raise ValueError("User must have a password")

        user = self.model(email=self.normalize_email(email), username=username)
        user.set_password(password)
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractUser):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    fullName = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=255, unique=True)
    is_user = models.BooleanField(default=True)   
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    first_name = None
    last_name = None
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]  # Ensures email is prompted when creating superuser

    objects = UserManager()
    
class Category(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    
class QuizInfo(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    time_limit = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='quiz_categories')
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='quiz_user')

class QuizQuestion(models.Model):
    QUESTION_TYPES = (
        ("single", "Single choice"),
        ("multiple", "Multiple choice"),
    )

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    question = models.TextField()
    question_no = models.IntegerField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default="single")
    points = models.FloatField(default=10.0)   
    quiz_info = models.ForeignKey("QuizInfo", on_delete=models.CASCADE, related_name='quiz_info_questions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def correct_options(self):
        return self.options.filter(is_correct=True)

class QuizOption(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='quiz_question_options')
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(null=True, blank=True)  # optional ordering field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        
class QuizAttempt(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_quiz_attempts')
    quiz_info = models.ForeignKey(QuizInfo, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(default=0.0)   # accumulated score

class AnswerSubmission(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='attempt_answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_option_ids = models.JSONField()   # list of UUIDs (strings)
    is_correct = models.BooleanField()
    awarded_points = models.FloatField(default=0.0)
    answered_at = models.DateTimeField(auto_now_add=True)