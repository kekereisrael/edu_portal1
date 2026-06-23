"""
Models for the exams app - Exam management, questions, attempts, and results.
Phase 6B additions: QuestionBank, QuestionCategory, QuestionTag, BankQuestion,
ExamCategory, and exam-generation helpers.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel, SchoolScopedModel


class Exam(SchoolScopedModel):
    """An exam created by a teacher for a subject."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ACTIVE = 'active', 'Active'
        CLOSED = 'closed', 'Closed'
        ARCHIVED = 'archived', 'Archived'

    class ExamType(models.TextChoices):
        CBT = 'cbt', 'Computer-Based Test'
        QUIZ = 'quiz', 'Quiz'
        PRACTICE = 'practice', 'Practice Test'
        ASSIGNMENT = 'assignment', 'Assignment'

    title = models.CharField(max_length=200)
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='exams',
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams',
        db_index=True,
    )
    exam_type = models.CharField(
        max_length=20, choices=ExamType.choices, default=ExamType.CBT, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    instructions = models.TextField(blank=True, null=True)
    duration_minutes = models.IntegerField(
        default=60, help_text='Exam duration in minutes'
    )
    passing_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=50.0,
        help_text='Minimum score percentage to pass'
    )
    total_marks = models.IntegerField(default=0)
    shuffle_questions = models.BooleanField(default=False)
    shuffle_options = models.BooleanField(default=False)
    show_result_immediately = models.BooleanField(default=True)
    allow_review = models.BooleanField(
        default=True, help_text='Allow students to review answers after submission'
    )
    max_attempts = models.IntegerField(
        default=1, help_text='Maximum number of attempts allowed (0 = unlimited)'
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams',
    )

    class Meta:
        verbose_name = 'exam'
        verbose_name_plural = 'exams'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'status'], name='idx_exam_school_status'),
            models.Index(fields=['school', 'subject'], name='idx_exam_school_subject'),
            models.Index(fields=['created_by', 'status'], name='idx_exam_creator_status'),
        ]

    def __str__(self):
        return f'{self.title} ({self.subject.code})'

    @property
    def question_count(self):
        return self.questions.filter(is_active=True).count()

    @property
    def is_available(self):
        """Check if exam is currently available for students."""
        if self.status != self.Status.PUBLISHED:
            return False
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    def publish(self):
        self.status = self.Status.PUBLISHED
        self.save(update_fields=['status', 'updated_at'])

    def close(self):
        self.status = self.Status.CLOSED
        self.save(update_fields=['status', 'updated_at'])

    def recalculate_total_marks(self):
        """Recalculate total marks from active questions."""
        total = self.questions.filter(is_active=True).aggregate(
            total=models.Sum('marks')
        )['total'] or 0
        self.total_marks = total
        self.save(update_fields=['total_marks', 'updated_at'])


class Question(BaseModel):
    """A question in an exam."""

    class DifficultyLevel(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class QuestionType(models.TextChoices):
        MCQ = 'mcq', 'Multiple Choice'
        TRUE_FALSE = 'true_false', 'True/False'
        SHORT_ANSWER = 'short_answer', 'Short Answer'

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='questions', db_index=True
    )
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ
    )
    option_a = models.CharField(max_length=500, blank=True, null=True)
    option_b = models.CharField(max_length=500, blank=True, null=True)
    option_c = models.CharField(max_length=500, blank=True, null=True)
    option_d = models.CharField(max_length=500, blank=True, null=True)
    correct_answer = models.CharField(
        max_length=10,
        help_text='For MCQ: "A", "B", "C", or "D". For True/False: "True" or "False".'
    )
    explanation = models.TextField(
        blank=True, null=True,
        help_text='Explanation shown after submission'
    )
    difficulty = models.CharField(
        max_length=10, choices=DifficultyLevel.choices, default=DifficultyLevel.MEDIUM
    )
    marks = models.IntegerField(default=1)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    topic = models.ForeignKey(
        'subjects.Topic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
    )

    class Meta:
        verbose_name = 'question'
        verbose_name_plural = 'questions'
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['exam', 'is_active'], name='idx_question_exam_active'),
            models.Index(fields=['exam', 'difficulty'], name='idx_question_exam_diff'),
        ]

    def __str__(self):
        return f'Q{self.order}: {self.question_text[:80]}'

    @property
    def school(self):
        return self.exam.school


class ExamAttempt(BaseModel):
    """A student's attempt at an exam."""

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        TIMED_OUT = 'timed_out', 'Timed Out'
        GRADED = 'graded', 'Graded'
        ABANDONED = 'abandoned', 'Abandoned'

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='attempts', db_index=True
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_attempts',
        db_index=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(default=0)
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Raw score (marks obtained)'
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Score as percentage'
    )
    passed = models.BooleanField(null=True, blank=True)
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    wrong_answers = models.IntegerField(default=0)
    skipped_answers = models.IntegerField(default=0)
    attempt_number = models.IntegerField(default=1)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'exam attempt'
        verbose_name_plural = 'exam attempts'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'exam'], name='idx_attempt_student_exam'),
            models.Index(fields=['exam', 'status'], name='idx_attempt_exam_status'),
            models.Index(fields=['student', 'status'], name='idx_attempt_student_status'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.exam.title} (Attempt {self.attempt_number})'

    @property
    def school(self):
        return self.exam.school

    @property
    def time_remaining_seconds(self):
        """Calculate remaining time in seconds."""
        if self.status != self.Status.IN_PROGRESS:
            return 0
        elapsed = (timezone.now() - self.started_at).total_seconds()
        remaining = (self.exam.duration_minutes * 60) - elapsed
        return max(0, int(remaining))

    @property
    def is_timed_out(self):
        return self.time_remaining_seconds == 0 and self.status == self.Status.IN_PROGRESS

    def submit(self, auto=False):
        """Submit the exam attempt and calculate score."""
        self.submitted_at = timezone.now()
        self.time_taken_seconds = int(
            (self.submitted_at - self.started_at).total_seconds()
        )
        self.status = self.Status.TIMED_OUT if auto else self.Status.SUBMITTED

        # Calculate score
        answers = self.answers.select_related('question')
        total_marks = 0
        earned_marks = 0
        correct = 0
        wrong = 0
        skipped = 0

        for answer in answers:
            q = answer.question
            total_marks += q.marks
            if answer.selected_answer is None or answer.selected_answer == '':
                skipped += 1
            elif answer.is_correct:
                earned_marks += q.marks
                correct += 1
            else:
                wrong += 1

        self.score = earned_marks
        self.total_questions = answers.count()
        self.correct_answers = correct
        self.wrong_answers = wrong
        self.skipped_answers = skipped

        if total_marks > 0:
            self.percentage = round((earned_marks / total_marks) * 100, 2)
        else:
            self.percentage = 0

        self.passed = self.percentage >= self.exam.passing_score
        self.status = self.Status.GRADED
        self.save()
        return self


class ExamAnswer(BaseModel):
    """A student's answer to a specific question in an attempt."""

    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name='answers', db_index=True
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='student_answers', db_index=True
    )
    selected_answer = models.CharField(
        max_length=500, blank=True, null=True,
        help_text='The answer selected/entered by the student'
    )
    is_correct = models.BooleanField(null=True, blank=True)
    is_marked_for_review = models.BooleanField(default=False)
    time_spent_seconds = models.IntegerField(default=0)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'exam answer'
        verbose_name_plural = 'exam answers'
        unique_together = ['attempt', 'question']
        indexes = [
            models.Index(fields=['attempt', 'is_correct'], name='idx_answer_attempt_correct'),
        ]

    def __str__(self):
        return f'{self.attempt.student.full_name} - Q{self.question.order}: {self.selected_answer}'

    @property
    def school(self):
        return self.attempt.exam.school

    def save(self, *args, **kwargs):
        # Auto-grade MCQ and True/False
        if self.selected_answer is not None and self.question.question_type in (
            Question.QuestionType.MCQ, Question.QuestionType.TRUE_FALSE
        ):
            self.is_correct = (
                self.selected_answer.strip().upper() ==
                self.question.correct_answer.strip().upper()
            )
        super().save(*args, **kwargs)


class ExamResult(BaseModel):
    """Aggregated result record for a student's best/final attempt."""

    attempt = models.OneToOneField(
        ExamAttempt, on_delete=models.CASCADE, related_name='result'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_results',
        db_index=True,
    )
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='results', db_index=True
    )
    score = models.DecimalField(max_digits=5, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    passed = models.BooleanField()
    grade = models.CharField(max_length=5, blank=True, null=True)
    rank = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'exam result'
        verbose_name_plural = 'exam results'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'exam'], name='idx_result_student_exam'),
            models.Index(fields=['exam', 'percentage'], name='idx_result_exam_pct'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.exam.title}: {self.percentage}%'

    @property
    def school(self):
        return self.exam.school


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6B — QUESTION BANK & EXAM PREPARATION SYSTEM
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Exam Category (School Exam, WAEC, NECO, JAMB, BECE, NABTEB)
# ─────────────────────────────────────────────────────────────────────────────

class ExamCategory(models.Model):
    """
    Top-level category for a question or exam.
    Covers both internal school exams and major Nigerian public examinations.
    """

    class CategoryCode(models.TextChoices):
        SCHOOL_EXAM = 'school_exam', 'School Exam'
        WAEC = 'waec', 'WAEC'
        NECO = 'neco', 'NECO'
        JAMB = 'jamb', 'JAMB (UTME)'
        BECE = 'bece', 'BECE'
        NABTEB = 'nabteb', 'NABTEB'
        MOCK = 'mock', 'Mock Exam'
        PRACTICE = 'practice', 'Practice / Revision'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=20, choices=CategoryCode.choices, unique=True, db_index=True
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(
        default=False,
        help_text='Public exam categories (WAEC, NECO, JAMB…) are shared across all schools.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'exam category'
        verbose_name_plural = 'exam categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Question Category & Tag
# ─────────────────────────────────────────────────────────────────────────────

class QuestionCategory(SchoolScopedModel):
    """
    Hierarchical category for organising questions within a school's bank.
    e.g.  Mathematics → Algebra → Quadratic Equations
    """

    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'question category'
        verbose_name_plural = 'question categories'
        unique_together = ['school', 'name', 'parent']
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} → {self.name}'
        return self.name


class QuestionTag(SchoolScopedModel):
    """
    Free-form tag for questions, e.g. 'algebra', '2023-waec', 'tricky'.
    Tags are school-scoped so each school manages its own vocabulary.
    """

    name = models.CharField(max_length=50)
    color = models.CharField(
        max_length=7, default='#6366f1',
        help_text='Hex colour for UI display, e.g. #6366f1',
    )

    class Meta:
        verbose_name = 'question tag'
        verbose_name_plural = 'question tags'
        unique_together = ['school', 'name']
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Question Bank & Bank Question
# ─────────────────────────────────────────────────────────────────────────────

class QuestionBank(SchoolScopedModel):
    """
    A named collection of reusable questions for a school.
    A school can have multiple banks (e.g. 'JSS Mathematics Bank', 'WAEC Past Questions').
    """

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='question_banks',
        db_index=True,
    )
    exam_category = models.ForeignKey(
        ExamCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_banks',
    )
    class_level = models.ForeignKey(
        'schools.ClassLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_banks',
        help_text='Target class level (JSS1–SSS3)',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_question_banks',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_shared = models.BooleanField(
        default=False,
        help_text='If True, all teachers in the school can use this bank.',
    )

    class Meta:
        verbose_name = 'question bank'
        verbose_name_plural = 'question banks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'subject'], name='idx_qbank_school_subject'),
            models.Index(fields=['school', 'is_active'], name='idx_qbank_school_active'),
        ]

    def __str__(self):
        return f'{self.name} ({self.school.name})'

    @property
    def question_count(self):
        return self.bank_questions.filter(is_active=True).count()


class BankQuestion(BaseModel):
    """
    A reusable question stored in a QuestionBank.
    Supports MCQ, True/False, and Short Answer.
    Can be tagged, categorised, and linked to a topic.
    """

    class DifficultyLevel(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class QuestionType(models.TextChoices):
        MCQ = 'mcq', 'Multiple Choice'
        TRUE_FALSE = 'true_false', 'True/False'
        SHORT_ANSWER = 'short_answer', 'Short Answer'

    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='bank_questions',
        db_index=True,
    )
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ, db_index=True
    )
    # MCQ options
    option_a = models.CharField(max_length=500, blank=True, null=True)
    option_b = models.CharField(max_length=500, blank=True, null=True)
    option_c = models.CharField(max_length=500, blank=True, null=True)
    option_d = models.CharField(max_length=500, blank=True, null=True)
    correct_answer = models.CharField(
        max_length=500,
        help_text='MCQ: "A"/"B"/"C"/"D". True/False: "True"/"False". Short answer: the expected answer.',
    )
    explanation = models.TextField(blank=True, null=True)
    difficulty = models.CharField(
        max_length=10, choices=DifficultyLevel.choices, default=DifficultyLevel.MEDIUM, db_index=True
    )
    marks = models.PositiveSmallIntegerField(default=1)
    # Taxonomy
    topic = models.ForeignKey(
        'subjects.Topic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_questions',
    )
    category = models.ForeignKey(
        QuestionCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_questions',
    )
    tags = models.ManyToManyField(
        QuestionTag,
        blank=True,
        related_name='bank_questions',
    )
    # Exam type association
    exam_category = models.ForeignKey(
        ExamCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_questions',
    )
    exam_year = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Year the question appeared in a public exam (e.g. 2019)',
    )
    # Metadata
    image = models.ImageField(
        upload_to='question_images/', blank=True, null=True,
        help_text='Optional image/diagram for the question',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    times_used = models.PositiveIntegerField(
        default=0, help_text='How many times this question has been added to an exam'
    )
    # Import tracking
    import_source = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='Source of import: csv, excel, manual, etc.',
    )
    import_batch = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Batch identifier for bulk imports',
    )

    class Meta:
        verbose_name = 'bank question'
        verbose_name_plural = 'bank questions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bank', 'difficulty'], name='idx_bq_bank_diff'),
            models.Index(fields=['bank', 'question_type'], name='idx_bq_bank_type'),
            models.Index(fields=['bank', 'is_active'], name='idx_bq_bank_active'),
            models.Index(fields=['bank', 'topic'], name='idx_bq_bank_topic'),
            models.Index(fields=['exam_category', 'exam_year'], name='idx_bq_cat_year'),
        ]

    def __str__(self):
        return f'{self.question_text[:80]} [{self.get_difficulty_display()}]'

    @property
    def school(self):
        return self.bank.school

    def increment_usage(self):
        """Increment the times_used counter when added to an exam."""
        self.times_used += 1
        self.save(update_fields=['times_used', 'updated_at'])


# ─────────────────────────────────────────────────────────────────────────────
# TASK 5 — Exam ↔ BankQuestion link (questions pulled from bank into an exam)
# ─────────────────────────────────────────────────────────────────────────────

class ExamBankQuestion(BaseModel):
    """
    Links a BankQuestion into a specific Exam as one of its questions.
    Keeps a snapshot of the question text/options at the time of linking
    so edits to the bank question don't break live exams.
    """

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='bank_question_links',
        db_index=True,
    )
    bank_question = models.ForeignKey(
        BankQuestion,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_links',
        db_index=True,
    )
    # Snapshot fields (copied from BankQuestion at link time)
    question_text = models.TextField()
    question_type = models.CharField(max_length=20)
    option_a = models.CharField(max_length=500, blank=True, null=True)
    option_b = models.CharField(max_length=500, blank=True, null=True)
    option_c = models.CharField(max_length=500, blank=True, null=True)
    option_d = models.CharField(max_length=500, blank=True, null=True)
    correct_answer = models.CharField(max_length=500)
    explanation = models.TextField(blank=True, null=True)
    difficulty = models.CharField(max_length=10)
    marks = models.PositiveSmallIntegerField(default=1)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'exam bank question'
        verbose_name_plural = 'exam bank questions'
        unique_together = ['exam', 'bank_question']
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.exam.title} ← {self.question_text[:60]}'

    @property
    def school(self):
        return self.exam.school

    def save(self, *args, **kwargs):
        # Auto-snapshot from bank_question on first save
        if self.bank_question and not self.pk:
            bq = self.bank_question
            self.question_text = bq.question_text
            self.question_type = bq.question_type
            self.option_a = bq.option_a
            self.option_b = bq.option_b
            self.option_c = bq.option_c
            self.option_d = bq.option_d
            self.correct_answer = bq.correct_answer
            self.explanation = bq.explanation
            self.difficulty = bq.difficulty
            self.marks = bq.marks
            bq.increment_usage()
        super().save(*args, **kwargs)


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6C — PRACTICE MODE, MOCK EXAMS & STUDENT IMPROVEMENT
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Practice Session
# Unlimited attempts, instant feedback, shows correct answer + explanation.
# Draws questions from a QuestionBank (not a formal Exam).
# ─────────────────────────────────────────────────────────────────────────────

class PracticeSession(BaseModel):
    """
    A student's practice session drawn from a QuestionBank.
    Unlimited attempts; instant feedback after each answer.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        ABANDONED = 'abandoned', 'Abandoned'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_sessions',
        db_index=True,
    )
    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='practice_sessions',
        db_index=True,
    )
    # Optional filters applied when the session was created
    topic = models.ForeignKey(
        'subjects.Topic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='practice_sessions',
    )
    difficulty = models.CharField(
        max_length=10,
        choices=BankQuestion.DifficultyLevel.choices,
        blank=True,
        null=True,
    )
    question_type = models.CharField(
        max_length=20,
        choices=BankQuestion.QuestionType.choices,
        blank=True,
        null=True,
    )
    num_questions = models.PositiveSmallIntegerField(
        default=10,
        help_text='Number of questions selected for this session',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'practice session'
        verbose_name_plural = 'practice sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'bank'], name='idx_practice_student_bank'),
            models.Index(fields=['student', 'status'], name='idx_practice_student_status'),
        ]

    def __str__(self):
        return f'{self.student.full_name} – Practice ({self.bank.name})'

    @property
    def school(self):
        return self.bank.school

    @property
    def total_answered(self):
        return self.practice_answers.count()

    @property
    def total_correct(self):
        return self.practice_answers.filter(is_correct=True).count()

    @property
    def score_percent(self):
        answered = self.total_answered
        if answered == 0:
            return 0
        return round((self.total_correct / answered) * 100, 1)

    def complete(self):
        from django.utils import timezone
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class PracticeAnswer(BaseModel):
    """
    A student's answer to a single question in a PracticeSession.
    Instant feedback: is_correct, correct_answer, and explanation are
    returned immediately after submission.
    """

    session = models.ForeignKey(
        PracticeSession,
        on_delete=models.CASCADE,
        related_name='practice_answers',
        db_index=True,
    )
    bank_question = models.ForeignKey(
        BankQuestion,
        on_delete=models.CASCADE,
        related_name='practice_answers',
        db_index=True,
    )
    selected_answer = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Answer submitted by the student',
    )
    is_correct = models.BooleanField(null=True, blank=True)
    time_spent_seconds = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'practice answer'
        verbose_name_plural = 'practice answers'
        # Allow re-attempts on the same question within a session
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'bank_question'], name='idx_pans_session_bq'),
            models.Index(fields=['session', 'is_correct'], name='idx_pans_session_correct'),
        ]

    def __str__(self):
        status = 'Correct' if self.is_correct else 'Wrong'
        return f'{self.session.student.full_name} – {self.bank_question.question_text[:60]} [{status}]'

    @property
    def school(self):
        return self.session.bank.school

    def save(self, *args, **kwargs):
        # Auto-grade on save
        if self.selected_answer is not None and self.bank_question_id:
            bq = self.bank_question
            if bq.question_type in (
                BankQuestion.QuestionType.MCQ,
                BankQuestion.QuestionType.TRUE_FALSE,
            ):
                self.is_correct = (
                    self.selected_answer.strip().upper() ==
                    bq.correct_answer.strip().upper()
                )
            else:
                # Short answer: case-insensitive exact match
                self.is_correct = (
                    self.selected_answer.strip().lower() ==
                    bq.correct_answer.strip().lower()
                )
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Mock Exam Session
# Simulates a real exam: timer, randomised questions, real exam interface,
# score summary. Draws from a QuestionBank (not a formal Exam record).
# ─────────────────────────────────────────────────────────────────────────────

class MockExamSession(BaseModel):
    """
    A timed mock exam session drawn from a QuestionBank.
    Mimics the real CBT experience: timer, no instant feedback,
    full score summary on submission.
    """

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        TIMED_OUT = 'timed_out', 'Timed Out'
        ABANDONED = 'abandoned', 'Abandoned'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mock_exam_sessions',
        db_index=True,
    )
    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='mock_exam_sessions',
        db_index=True,
    )
    exam_category = models.ForeignKey(
        ExamCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mock_exam_sessions',
        help_text='e.g. WAEC, NECO, JAMB — for context display',
    )
    topic = models.ForeignKey(
        'subjects.Topic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mock_exam_sessions',
    )
    difficulty = models.CharField(
        max_length=10,
        choices=BankQuestion.DifficultyLevel.choices,
        blank=True,
        null=True,
    )
    num_questions = models.PositiveSmallIntegerField(default=40)
    duration_minutes = models.PositiveSmallIntegerField(
        default=60,
        help_text='Allocated time in minutes',
    )
    passing_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=50.0,
        help_text='Minimum percentage to pass',
    )
    shuffle_questions = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(default=0)
    # Score summary (populated on submission)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    wrong_answers = models.IntegerField(default=0)
    skipped_answers = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'mock exam session'
        verbose_name_plural = 'mock exam sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'bank'], name='idx_mock_student_bank'),
            models.Index(fields=['student', 'status'], name='idx_mock_student_status'),
        ]

    def __str__(self):
        return f'{self.student.full_name} – Mock ({self.bank.name}) [{self.status}]'

    @property
    def school(self):
        return self.bank.school

    @property
    def time_remaining_seconds(self):
        if self.status != self.Status.IN_PROGRESS:
            return 0
        elapsed = (timezone.now() - self.started_at).total_seconds()
        remaining = (self.duration_minutes * 60) - elapsed
        return max(0, int(remaining))

    @property
    def is_timed_out(self):
        return self.time_remaining_seconds == 0 and self.status == self.Status.IN_PROGRESS

    def submit(self, auto=False):
        """Grade and finalise the mock exam session."""
        self.submitted_at = timezone.now()
        self.time_taken_seconds = int(
            (self.submitted_at - self.started_at).total_seconds()
        )
        self.status = self.Status.TIMED_OUT if auto else self.Status.SUBMITTED

        answers = self.mock_answers.select_related('bank_question')
        total_marks = 0
        earned_marks = 0
        correct = wrong = skipped = 0

        for ans in answers:
            bq = ans.bank_question
            total_marks += bq.marks
            if not ans.selected_answer:
                skipped += 1
            elif ans.is_correct:
                earned_marks += bq.marks
                correct += 1
            else:
                wrong += 1

        self.score = earned_marks
        self.total_questions = answers.count()
        self.correct_answers = correct
        self.wrong_answers = wrong
        self.skipped_answers = skipped
        self.percentage = round((earned_marks / total_marks) * 100, 2) if total_marks > 0 else 0
        self.passed = self.percentage >= self.passing_score
        self.status = self.Status.SUBMITTED if not auto else self.Status.TIMED_OUT
        self.save()
        return self


class MockExamAnswer(BaseModel):
    """
    A student's answer to a single question in a MockExamSession.
    No instant feedback — results shown only after submission.
    """

    session = models.ForeignKey(
        MockExamSession,
        on_delete=models.CASCADE,
        related_name='mock_answers',
        db_index=True,
    )
    bank_question = models.ForeignKey(
        BankQuestion,
        on_delete=models.CASCADE,
        related_name='mock_answers',
        db_index=True,
    )
    selected_answer = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )
    is_correct = models.BooleanField(null=True, blank=True)
    is_marked_for_review = models.BooleanField(default=False)
    time_spent_seconds = models.IntegerField(default=0)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'mock exam answer'
        verbose_name_plural = 'mock exam answers'
        unique_together = ['session', 'bank_question']
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'is_correct'], name='idx_mans_session_correct'),
        ]

    def __str__(self):
        return f'{self.session.student.full_name} – {self.bank_question.question_text[:60]}'

    @property
    def school(self):
        return self.session.bank.school

    def save(self, *args, **kwargs):
        # Auto-grade on save
        if self.selected_answer is not None and self.bank_question_id:
            bq = self.bank_question
            if bq.question_type in (
                BankQuestion.QuestionType.MCQ,
                BankQuestion.QuestionType.TRUE_FALSE,
            ):
                self.is_correct = (
                    self.selected_answer.strip().upper() ==
                    bq.correct_answer.strip().upper()
                )
            else:
                self.is_correct = (
                    self.selected_answer.strip().lower() ==
                    bq.correct_answer.strip().lower()
                )
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Topic Performance (Weak/Strong Area Detection)
# Aggregated per student × topic × school.
# Updated after every PracticeSession and MockExamSession submission.
# ─────────────────────────────────────────────────────────────────────────────

class TopicPerformance(BaseModel):
    """
    Aggregated performance of a student on a specific topic.
    Recalculated after each practice/mock session that touches the topic.
    Used to classify topics as Weak, Average, or Strong.
    """

    class StrengthLevel(models.TextChoices):
        WEAK = 'weak', 'Weak'
        AVERAGE = 'average', 'Average'
        STRONG = 'strong', 'Strong'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='topic_performances',
        db_index=True,
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='topic_performances',
        db_index=True,
    )
    topic = models.ForeignKey(
        'subjects.Topic',
        on_delete=models.CASCADE,
        related_name='performances',
        db_index=True,
    )
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='topic_performances',
        db_index=True,
    )
    # Cumulative counters
    total_attempts = models.PositiveIntegerField(default=0)
    total_correct = models.PositiveIntegerField(default=0)
    total_wrong = models.PositiveIntegerField(default=0)
    # Derived
    accuracy_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Correct / Total * 100',
    )
    strength_level = models.CharField(
        max_length=10,
        choices=StrengthLevel.choices,
        default=StrengthLevel.AVERAGE,
        db_index=True,
    )
    last_practiced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'topic performance'
        verbose_name_plural = 'topic performances'
        unique_together = ['student', 'topic']
        ordering = ['accuracy_percent']
        indexes = [
            models.Index(fields=['student', 'school', 'strength_level'], name='idx_tp_student_school_strength'),
            models.Index(fields=['student', 'subject'], name='idx_tp_student_subject'),
        ]

    def __str__(self):
        return (
            f'{self.student.full_name} – {self.topic.name}: '
            f'{self.accuracy_percent}% ({self.strength_level})'
        )

    # ── Thresholds ────────────────────────────────────────────────────────────
    WEAK_THRESHOLD = 50      # < 50% → Weak
    STRONG_THRESHOLD = 75    # ≥ 75% → Strong

    def recalculate(self):
        """Recompute accuracy and strength level from counters."""
        from django.utils import timezone
        if self.total_attempts > 0:
            self.accuracy_percent = round(
                (self.total_correct / self.total_attempts) * 100, 2
            )
        else:
            self.accuracy_percent = 0

        if self.accuracy_percent < self.WEAK_THRESHOLD:
            self.strength_level = self.StrengthLevel.WEAK
        elif self.accuracy_percent >= self.STRONG_THRESHOLD:
            self.strength_level = self.StrengthLevel.STRONG
        else:
            self.strength_level = self.StrengthLevel.AVERAGE

        self.last_practiced_at = timezone.now()
        self.save(update_fields=[
            'accuracy_percent', 'strength_level',
            'last_practiced_at', 'updated_at',
        ])

    @classmethod
    def record_answer(cls, student, topic, subject, school, is_correct: bool):
        """
        Increment counters for a student's answer on a topic.
        Creates the record if it doesn't exist yet.
        """
        obj, _ = cls.objects.get_or_create(
            student=student,
            topic=topic,
            defaults={
                'school': school,
                'subject': subject,
            },
        )
        obj.total_attempts += 1
        if is_correct:
            obj.total_correct += 1
        else:
            obj.total_wrong += 1
        obj.save(update_fields=['total_attempts', 'total_correct', 'total_wrong', 'updated_at'])
        obj.recalculate()
        return obj
