from random import randint, choice, sample
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from faker import Faker

from core.models import QuizInfo, QuizQuestion, QuizOption, Category

User = get_user_model()

class Command(BaseCommand):
    help = "Seed QuizInfo, QuizQuestion and QuizOption data (20 quizzes x 5 questions each)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quizzes",
            type=int,
            default=20,
            help="Number of QuizInfo records to create (default: 20).",
        )
        parser.add_argument(
            "--questions-per-quiz",
            type=int,
            default=5,
            help="Number of questions per quiz (default: 5).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        faker = Faker("id_ID")
        num_quizzes = options["quizzes"]
        q_per_quiz = options["questions_per_quiz"]

        # ensure we have some users to assign quizzes to
        users = list(User.objects.all())

        # ensure we have some categories to rotate
        categories = list(Category.objects.all())

        created_quizzes = 0
        for i in range(num_quizzes):
            owner = users[i % len(users)]
            category = categories[i % len(categories)]
            # Make sure name is unique: include index
            quiz_name = f"{faker.sentence(nb_words=3).rstrip('.')} - Quiz {i+1}"

            time_limit = randint(600, 7200)  # 10min - 2 hours in seconds (random)
            # create quiz
            quiz = QuizInfo.objects.create(
                name=quiz_name,
                time_limit=time_limit,
                category=category,
                user=owner
            )

            # create questions for this quiz
            for qno in range(1, q_per_quiz + 1):
                question_text = faker.sentence(nb_words=10)
                # randomize type
                qtype = choice(["single", "multiple"])
                points = float(choice([5, 10, 15, 20, 25, 30]))

                question = QuizQuestion.objects.create(
                    question=question_text,
                    question_no=qno,
                    question_type=qtype,
                    points=points,
                    quiz_info=quiz
                )

                # create 3-5 options
                num_options = randint(3, 5)
                option_texts = [faker.sentence(nb_words=4).rstrip('.') for _ in range(num_options)]

                if qtype == "single":
                    # exactly one correct
                    correct_idx = randint(0, num_options - 1)
                    correct_set = {correct_idx}
                else:
                    # multiple: choose 1 .. min(3, num_options) correct options
                    max_correct = min(3, num_options)
                    k = randint(1, max_correct)
                    correct_set = set(sample(range(num_options), k))

                for idx, text in enumerate(option_texts, start=1):
                    is_correct = (idx - 1) in correct_set
                    QuizOption.objects.create(
                        question=question,
                        text=text,
                        is_correct=is_correct,
                        order=idx
                    )

            created_quizzes += 1
            self.stdout.write(self.style.SUCCESS(f"Created quiz {created_quizzes}/{num_quizzes}: {quiz_name} (owner={owner.username}, category={category.name})"))

        self.stdout.write(self.style.SUCCESS("🌱 Seeding completed: "
                                             f"{created_quizzes} quizzes, "
                                             f"{created_quizzes * q_per_quiz} questions, "
                                             "and options created."))
