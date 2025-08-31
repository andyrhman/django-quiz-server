from rest_framework import serializers
from core.models import QuizQuestion, QuizOption, QuizInfo

class QuizOptionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = QuizOption
        fields = ('id', 'text', 'is_correct', 'order', 'created_at', 'updated_at')
        read_only_fields = ('created_at','updated_at')

# READ serializer used for general endpoints (non-preview).
# explanation visible only to owner/admin; otherwise null.
class QuizQuestionSerializer(serializers.ModelSerializer):
    options = QuizOptionSerializer(source='quiz_question_options', many=True, read_only=True)
    quiz_info = serializers.PrimaryKeyRelatedField(read_only=True)
    explanation = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = QuizQuestion
        fields = (
            'id','question','question_no','question_type','points',
            'quiz_info','created_at','updated_at','options','explanation'
        )
        read_only_fields = ('id','created_at','updated_at','explanation')

    def get_explanation(self, obj):
        request = self.context.get('request', None)
        if request is None:
            return None
        token = getattr(request, 'auth', None)
        # robust scope detection
        scope = None
        try:
            scope = token.get('scope') if token and hasattr(token, 'get') else getattr(token, 'scope', None)
        except Exception:
            scope = getattr(token, 'scope', None)

        # Admin can see explanation
        if scope == 'admin':
            return obj.explanation

        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            # owner sees explanation
            try:
                if str(obj.quiz_info.user_id) == str(user.id):
                    return obj.explanation
            except Exception:
                if obj.quiz_info.user == user:
                    return obj.explanation
        return None


# CREATE/UPDATE serializer: accept explanation field
class QuizQuestionCreateUpdateSerializer(serializers.ModelSerializer):
    quiz_info = serializers.UUIDField(write_only=True)
    options = QuizOptionSerializer(many=True, write_only=True)
    explanation = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = QuizQuestion
        fields = ('id','question','question_no','question_type','points','explanation','quiz_info','options')
        read_only_fields = ('id',)

    def validate(self, data):
        # Basic presence checks
        opts = data.get('options', [])
        if len(opts) < 2:
            raise serializers.ValidationError("A question must have at least 2 options.")

        qtype = data.get('question_type', getattr(self.instance, 'question_type', 'single'))
        correct_count = sum(1 for o in opts if o.get('is_correct'))
        if qtype == 'single' and correct_count != 1:
            raise serializers.ValidationError("Single choice must have exactly one correct option.")
        if qtype == 'multiple' and correct_count < 1:
            raise serializers.ValidationError("Multiple choice must have at least one correct option.")

        # Validate quiz_info exists
        quiz_info_id = data.get('quiz_info')
        try:
            quiz = QuizInfo.objects.get(id=quiz_info_id)
        except QuizInfo.DoesNotExist:
            raise serializers.ValidationError("quiz_info does not exist")

        # optional: validate unique question_no per quiz
        qno = data.get('question_no')
        if qno is not None:
            qs = QuizQuestion.objects.filter(quiz_info=quiz, question_no=qno)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({"question_no": "question_no must be unique per quiz."})

        data['quiz_info'] = quiz
        return data

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        explanation = validated_data.pop('explanation', None)
        quiz_info = validated_data.pop('quiz_info')
        question = QuizQuestion.objects.create(quiz_info=quiz_info, explanation=explanation, **validated_data)
        for idx, opt in enumerate(options_data, start=1):
            QuizOption.objects.create(question=question, order=opt.get('order', idx), **opt)
        return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        explanation = validated_data.pop('explanation', None)

        # update simple fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # update explanation if provided (allow empty string)
        if explanation is not None:
            instance.explanation = explanation
        instance.save()

        # naive but reliable: delete and recreate options if provided
        if options_data is not None:
            instance.quiz_question_options.all().delete()
            for idx, opt in enumerate(options_data, start=1):
                QuizOption.objects.create(question=instance, order=opt.get('order', idx), **opt)

        return instance
