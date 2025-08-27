from rest_framework import serializers
from core.models import QuizAttempt, AnswerSubmission, QuizInfo, QuizQuestion, User

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'username', 'is_user',]
        extra_kwargs = {
            'password': {'write_only': True}
        }    

class AnswerSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerSubmission
        fields = ('id', 'question', 'selected_option_ids', 'is_correct', 'awarded_points', 'answered_at')

class QuizAttemptSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    percent_score = serializers.SerializerMethodField()
    answers = AnswerSubmissionSerializer(source='attempt_answers', many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = ('id', 'user', 'quiz_info', 'started_at', 'finished_at', 'score', 'percent_score', 'answers')

    def get_percent_score(self, obj):
        try:
            return obj.percent_score()
        except Exception:
            return 0.0
