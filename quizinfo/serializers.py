from rest_framework import serializers
from core.models import QuizInfo, Category, QuizOption, QuizQuestion, User

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'username', 'is_user',]
        extra_kwargs = {
            'password': {'write_only': True}
        }    
    
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name')
        
class QuizInfoSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    user = UserSerializer(read_only=True)
    max_score = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = QuizInfo
        fields = (
            "id",
            "name",
            "time_limit",
            "category",
            "user",
            "created_at",
            "updated_at",
            "max_score",
        )
        read_only_fields = ("id", "created_at", "updated_at", "max_score")

    def get_max_score(self, obj):
        # uses the model helper you already defined
        try:
            return obj.compute_max_score()
        except Exception:
            return 0.0

    def validate_time_limit(self, value):
        if value is None:
            return 0
        if value < 0:
            raise serializers.ValidationError("time_limit must be non-negative.")
        return value

class QuizInfoSerializerCreateUpdate(serializers.ModelSerializer):
    category = serializers.UUIDField(write_only=True)

    class Meta:
        model = QuizInfo
        fields = (
            "id",
            "name",
            "time_limit",
            "category",
            "user",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        
    def validate(self, data):
        try:
            category = Category.objects.get(id=data['category'])
        except Category.DoesNotExist:
            raise serializers.ValidationError("Category does not exist")
        data['category'] = category
        return data
    
    def create(self, validated_data):
        request = self.context['request']
        quiz_info = QuizInfo.objects.create(
            category=validated_data.pop('category'), 
            user=request.user,
            **validated_data
        )
        return quiz_info
   
    
class QuizOptionNestedSerializer(serializers.ModelSerializer):
    is_correct = serializers.SerializerMethodField()

    class Meta:
        model = QuizOption
        fields = ('id', 'text', 'order', 'is_correct')

    def get_is_correct(self, obj):
        request = self.context.get('request', None)
        if request is None:
            return None

        # Normalize token scope safely across token types
        token = getattr(request, 'auth', None)
        scope = None
        try:
            # token might be a dict-like payload
            scope = token.get('scope')
        except Exception:
            # token might be an object with attribute 'scope'
            scope = getattr(token, 'scope', None)

        # Admin scope always sees answers
        if scope == 'admin':
            return obj.is_correct

        # Owner (authenticated) sees answers
        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            # compare by id to avoid object equality pitfalls
            try:
                if str(obj.question.quiz_info.user_id) == str(user.id):
                    return obj.is_correct
            except Exception:
                # fallback to object comparison
                if obj.question.quiz_info.user == user:
                    return obj.is_correct

        # Otherwise hide the truth
        return None

class QuizQuestionNestedSerializer(serializers.ModelSerializer):
    """
    Nested question serializer including its options (read-only).
    """
    options = QuizOptionNestedSerializer(source='quiz_question_options', many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = (
            'id',
            'question',
            'question_no',
            'question_type',
            'points',
            'options',
        )


class QuizInfoDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for QuizInfo detail that includes all questions and their options.
    """
    category = CategorySerializer(read_only=True)
    user = UserSerializer(read_only=True)
    max_score = serializers.SerializerMethodField()
    questions = QuizQuestionNestedSerializer(source='quiz_info_questions', many=True, read_only=True)

    class Meta:
        model = QuizInfo
        fields = (
            "id",
            "name",
            "time_limit",
            "category",
            "user",
            "created_at",
            "updated_at",
            "max_score",
            "questions",
        )
        read_only_fields = ("id", "created_at", "updated_at", "max_score", "questions")

    def get_max_score(self, obj):
        try:
            return obj.compute_max_score()
        except Exception:
            return 0.0
        
class QuizOptionPreviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizOption
        fields = ('id', 'text', 'order', 'is_correct')  # preview shows is_correct flag

class QuizQuestionPreviewSerializer(serializers.ModelSerializer):
    options = QuizOptionPreviewSerializer(source='quiz_question_options', many=True, read_only=True)
    explanation = serializers.CharField(read_only=True)  # show explanation in preview always

    class Meta:
        model = QuizQuestion
        fields = ('id','question','question_no','question_type','points','options','explanation')
       