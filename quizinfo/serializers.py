from rest_framework import serializers
from core.models import QuizInfo, Category, User

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
        
        