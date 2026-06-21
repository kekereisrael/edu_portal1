"""
Models for the exams app - Exam creation, questions, attempts, and grading.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel, SchoolScopedModel


class QuestionBank(SchoolScopedModel):
    """Reusable question pool per subject."""

    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='question_banks',
        db_index=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_question_banks',
    )

    class Meta:
        verbose_name = 'question bank'
        verbose_name_plural = 'question banks'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.subject.code})'

    @property
    def question_count(self):
        return self.questions.count()


class QuestionTag(SchoolScopedModel):
    """Tags for categorizing questions (difficulty, bloom taxonomy, etc.)."""

    class TagType(models.TextChoices):
        DIFFICULTY = 'difficulty', 'Difficulty Level'
        BLOOM_TAXONOMY = 'bloom_taxonomy', 'Bloom Taxonomy'
        TOPIC = 'topic', 'Topic'
        CUSTOM = 'custom', 'Custom'

    name = models.CharField(max_length=50)
    tag_type = models.CharField(
        max_length=20, choices=TagType.choices, default=TagType.CUSTOM, db_index=True
    )

    class Meta:
        verbose_name = 'question tag'
        verbose_name_plural = 'question tags'
        unique_together = ['school', 'name', 'tag_type']
        ordering = ['tag_type', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_tag_type_display()})'


class Exam(SchoolScopedModel):
    """Exam/assessment definition."""

    class ExamType(models.TextChoices):
        QUIZ = 'quiz', 'Quiz'
        TEST = 'test', 'Test'
        MIDTERM = 'midterm', 'Midterm Exam'
        FINAL = 'final', 'Final Exam'
        ASSIGNMENT = 'assignment', 'Assignment'
        PRACTICE = 'practice', 'Practice'

    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='exams',
        db_index=True,
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='exams',
        db_index=True,
    )
    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams',
        help_text='Specific class this exam is for. Null means all enrolled students.',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    exam_type = models.CharField(
        max_length=20, choices=ExamType.choices, default=ExamType.TEST, db_index=True
    )
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    pass_marks = models.DecimalField(max_digits=6, decimal_places=2)
    duration_minutes = models.IntegerField(
        help_text='Duration in minutes. 0 means no time limit.'
    )
    start_time = models.DateTimeField(
        null=True, blank=True,
        help_text='When the exam becomes available',
    )
    end_time = models.DateTimeField(
        null=True, blank=True,
        help_text='When the exam closes',
    )
    is_published = models.BooleanField(default=False, db_index=True)
    is_proctored = models.BooleanField(default=False)
    shuffle_questions = models.BooleanField(default=False)
    shuffle_options = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=True)
    show_correct_answers = models.BooleanField(default=True)
    max_attempts = models.IntegerField(
        default=1, help_text='Maximum number of attempts allowed. -1 for unlimited.'
    )
    instructions = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams',
    )

    class Meta:
        verbose_name = 'exam'
        verbose_name_plural = 'exams'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'subject', 'term'], name='idx_exam_school_subj_term'),
            models.Index(fields=['school', 'is_published'], name='idx_exam_school_published'),
            models.Index(fields=['start_time', 'end_time'], name='idx_exam_time_window'),
        ]

    def __str__(self):
        return f'{self.title} ({self.subject.code})'

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def is_available(self):
        """Check if exam is currently available for taking."""
        if not self.is_published:
            return False
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True

    @property
    def is_upcoming(self):
        if not self.start_time:
            return False
        return timezone.now() < self.start_time

    @property
    def is_past(self):
        if not self.end_time:
            return False
        return timezone.now() > self.end_time


class ExamTemplate(SchoolScopedModel):
    """Predefined exam structures for quick exam creation."""

    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_templates',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    structure = models.JSONField(
        default=dict,
        help_text='Template structure: {"sections": [{"name": "MCQ", "question_count": 20, "marks_per_question": 2, "type": "mcq"}]}',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exam_templates',
    )

    class Meta:
        verbose_name = 'exam template'
        verbose_name_plural = 'exam templates'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}'


class ExamGroup(SchoolScopedModel):
    """Group exams together (e.g., all midterms for a term)."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='exam_groups',
        db_index=True,
    )
    exams = models.ManyToManyField(Exam, related_name='groups', blank=True)

    class Meta:
        verbose_name = 'exam group'
        verbose_name_plural = 'exam groups'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.term.name})'


class Question(BaseModel):
    """Question within an exam or question bank."""

    class QuestionType(models.TextChoices):
        MCQ = 'mcq', 'Multiple Choice'
        TRUE_FALSE = 'true_false', 'True/False'
        SHORT_ANSWER = 'short_answer', 'Short Answer'
        ESSAY = 'essay', 'Essay'
        FILL_BLANK = 'fill_blank', 'Fill in the Blank'
        MATCHING = 'matching', 'Matching'

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='questions',
        db_index=True,
    )
    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
    )
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ, db_index=True
    )
    text = models.TextField(help_text='The question text')
    explanation = models.TextField(
        blank=True, null=True,
        help_text='Explanation shown after answering',
    )
    marks = models.DecimalField(
        max_digits=5, decimal_places=2, default=1,
        help_text='Marks allocated for this question',
    )
    order = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True)
    image = models.ImageField(upload_to='questions/images/', blank=True, null=True)
    tags = models.ManyToManyField(QuestionTag, related_name='questions', blank=True)
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Additional metadata (AI generation info, difficulty score, etc.)',
    )

    class Meta:
        verbose_name = 'question'
        verbose_name_plural = 'questions'
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['exam', 'order'], name='idx_question_exam_order'),
            models.Index(fields=['question_bank', 'question_type'], name='idx_question_bank_type'),
        ]

    def __str__(self):
        return f'Q{self.order}: {self.text[:50]}...'

    @property
    def school(self):
        if self.exam:
            return self.exam.school
        if self.question_bank:
            return self.question_bank.school
        return None


class QuestionOption(BaseModel):
    """Answer option for a question (MCQ, True/False, Matching)."""

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='options', db_index=True
    )
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    image = models.ImageField(upload_to='questions/options/', blank=True, null=True)

    class Meta:
        verbose_name = 'question option'
        verbose_name_plural = 'question options'
        ordering = ['order']

    def __str__(self):
        correct = '✓' if self.is_correct else '✗'
        return f'{correct} {self.text[:50]}'


class ExamAttempt(BaseModel):
    """A student's attempt at taking an exam."""

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        GRADED = 'graded', 'Graded'
        TIMED_OUT = 'timed_out', 'Timed Out'

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='attempts', db_index=True
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_attempts',
        db_index=True,
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='exam_attempts',
        db_index=True,
        help_text='Denormalized for efficient school-level queries',
    )
    attempt_number = models.IntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    proctoring_data = models.JSONField(
        default=dict, blank=True,
        help_text='Proctoring events: tab switches, face detection, etc.',
    )
    time_spent_seconds = models.IntegerField(
        default=0, help_text='Total time spent in seconds'
    )

    class Meta:
        verbose_name = 'exam attempt'
        verbose_name_plural = 'exam attempts'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['exam', 'student', 'status'], name='idx_attempt_exam_student'),
            models.Index(fields=['school', 'submitted_at'], name='idx_attempt_school_submitted'),
            models.Index(fields=['student', 'status'], name='idx_attempt_student_status'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.exam.title} (Attempt {self.attempt_number})'

    @property
    def is_timed_out(self):
        """Check if the attempt has exceeded the time limit."""
        if self.exam.duration_minutes == 0:
            return False
        if self.status != self.Status.IN_PROGRESS:
            return False
        elapsed = (timezone.now() - self.started_at).total_seconds() / 60
        return elapsed > self.exam.duration_minutes

    @property
    def time_remaining_seconds(self):
        """Get remaining time in seconds."""
        if self.exam.duration_minutes == 0:
            return None
        elapsed = (timezone.now() - self.started_at).total_seconds()
        remaining = (self.exam.duration_minutes * 60) - elapsed
        return max(0, int(remaining))

    @property
    def passed(self):
        """Check if the student passed."""
        if self.score is None:
            return None
        return self.score >= self.exam.pass_marks

    def submit(self):
        """Submit the attempt and calculate score for auto-gradable questions."""
        self.submitted_at = timezone.now()
        self.time_spent_seconds = int(
            (self.submitted_at - self.started_at).total_seconds()
        )
        self.status = self.Status.SUBMITTED

        # Auto-grade MCQ, True/False, Fill-in-the-blank
        total_score = 0
        all_graded = True
        for answer in self.answers.select_related('question'):
            if answer.question.question_type in ['mcq', 'true_false', 'fill_blank']:
                answer.auto_grade()
                if answer.marks_awarded is not None:
                    total_score += answer.marks_awarded
            else:
                all_graded = False

        self.score = total_score
        if self.exam.total_marks > 0:
            self.percentage = (total_score / self.exam.total_marks) * 100

        if all_graded:
            self.status = self.Status.GRADED

        self.save()

    def timeout(self):
        """Mark attempt as timed out and auto-submit."""
        self.status = self.Status.TIMED_OUT
        self.submitted_at = timezone.now()
        self.time_spent_seconds = self.exam.duration_minutes * 60
        self.submit()


class Answer(BaseModel):
    """Student's answer to a question within an exam attempt."""

    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name='answers', db_index=True
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='answers', db_index=True
    )
    selected_option = models.ForeignKey(
        QuestionOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='selected_in_answers',
    )
    text_answer = models.TextField(
        blank=True, null=True,
        help_text='For short answer, essay, and fill-in-the-blank questions',
    )
    marks_awarded = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    is_correct = models.BooleanField(null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_answers',
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    ai_feedback = models.TextField(
        blank=True, null=True,
        help_text='AI-generated feedback for the answer',
    )
    teacher_feedback = models.TextField(
        blank=True, null=True,
        help_text='Teacher feedback for the answer',
    )

    class Meta:
        verbose_name = 'answer'
        verbose_name_plural = 'answers'
        unique_together = ['attempt', 'question']
        ordering = ['question__order']

    def __str__(self):
        return f'Answer to Q{self.question.order} by {self.attempt.student.full_name}'

    def auto_grade(self):
        """Auto-grade for objective question types."""
        question = self.question

        if question.question_type == 'mcq' or question.question_type == 'true_false':
            if self.selected_option and self.selected_option.is_correct:
                self.marks_awarded = question.marks
                self.is_correct = True
            else:
                self.marks_awarded = 0
                self.is_correct = False
        elif question.question_type == 'fill_blank':
            # Simple exact match (case-insensitive)
            correct_options = question.options.filter(is_correct=True)
            if self.text_answer and correct_options.exists():
                answer_lower = self.text_answer.strip().lower()
                for option in correct_options:
                    if option.text.strip().lower() == answer_lower:
                        self.marks_awarded = question.marks
                        self.is_correct = True
                        break
                else:
                    self.marks_awarded = 0
                    self.is_correct = False
            else:
                self.marks_awarded = 0
                self.is_correct = False

        self.graded_at = timezone.now()
        self.save(update_fields=['marks_awarded', 'is_correct', 'graded_at', 'updated_at'])

    def manual_grade(self, marks, graded_by, feedback=''):
        """Manually grade an answer (for essays, short answers)."""
        self.marks_awarded = marks
        self.is_correct = marks > 0
        self.graded_by = graded_by
        self.graded_at = timezone.now()
        self.teacher_feedback = feedback
        self.save(update_fields=[
            'marks_awarded', 'is_correct', 'graded_by',
            'graded_at', 'teacher_feedback', 'updated_at',
        ])


class Result(SchoolScopedModel):
    """Final result/grade for a student in a subject for a term."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='results',
        db_index=True,
    )
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='results',
        db_index=True,
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='results',
        db_index=True,
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='results',
        help_text='Specific exam this result is from (optional)',
    )
    score = models.DecimalField(max_digits=6, decimal_places=2)
    total_possible = models.DecimalField(
        max_digits=6, decimal_places=2, default=100
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    grade = models.CharField(
        max_length=5, blank=True, null=True,
        help_text='Letter grade (A, B, C, etc.)',
    )
    remarks = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_results',
    )

    class Meta:
        verbose_name = 'result'
        verbose_name_plural = 'results'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'term'], name='idx_result_student_term'),
            models.Index(fields=['school', 'subject', 'term'], name='idx_result_school_subj_term'),
            models.Index(fields=['school', 'is_published'], name='idx_result_school_published'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.subject.code}: {self.score}/{self.total_possible}'

    def save(self, *args, **kwargs):
        # Auto-calculate percentage
        if self.total_possible and self.total_possible > 0:
            self.percentage = (self.score / self.total_possible) * 100
        super().save(*args, **kwargs)

    def publish(self, published_by):
        """Publish this result to make it visible to students/parents."""
        self.is_published = True
        self.published_at = timezone.now()
        self.published_by = published_by
        self.save(update_fields=['is_published', 'published_at', 'published_by', 'updated_at'])
