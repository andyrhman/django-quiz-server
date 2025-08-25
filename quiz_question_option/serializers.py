from rest_framework import serializers
from core.models import QuizQuestion, QuizOption, QuizInfo 

class QuizOptionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)

    class Meta:
        model = QuizOption
        fields = ('id', 'text', 'is_correct', 'order', 'created_at', 'updated_at')
        read_only_fields = ('created_at','updated_at')

class QuizQuestionSerializer(serializers.ModelSerializer):
    """
    Read serializer for questions — returns nested options (read-only).
    """
    options = QuizOptionSerializer(source='quiz_question_options', many=True, read_only=True)
    quiz_info = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = QuizQuestion
        fields = (
            'id','question','question_no','question_type','points',
            'quiz_info','created_at','updated_at','options'
        )
        read_only_fields = ('id','created_at','updated_at')

class QuizQuestionCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating/updating a question with nested options.
    Expects:
    {
      "question": "...",
      "question_no": 1,
      "question_type": "single",
      "points": 10,
      "quiz_info": "<uuid>",
      "options": [
         {"text":"A", "is_correct": false},
         {"text":"B", "is_correct": true}
      ]
    }
    """
    quiz_info = serializers.UUIDField(write_only=True)
    options = QuizOptionSerializer(many=True, write_only=True)

    class Meta:
        model = QuizQuestion
        fields = ('id','question','question_no','question_type','points','quiz_info','options')
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

        # replace quiz_info uuid with actual instance for create/update convenience
        data['quiz_info'] = quiz
        return data

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        quiz_info = validated_data.pop('quiz_info')
        question = QuizQuestion.objects.create(quiz_info=quiz_info, **validated_data)
        for idx, opt in enumerate(options_data, start=1):
            QuizOption.objects.create(question=question, order=opt.get('order', idx), **opt)
        return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        # update simple fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # naive but reliable: delete and recreate options if provided
        if options_data is not None:
            instance.quiz_question_options.all().delete()
            for idx, opt in enumerate(options_data, start=1):
                QuizOption.objects.create(question=instance, order=opt.get('order', idx), **opt)

        return instance
