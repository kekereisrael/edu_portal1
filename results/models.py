"""
Models for the results app — Score Entry, Grading, Report Cards, Publishing.
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Avg, Max, Min, Count, Q


# ─────────────────────────────────────────────────────────────────────────────
# GRADE CONFIGURATION  (school-level grading scale)
# ─────────────────────────────────────────────────────────────────────────────

class GradeConfig(models.Model):
    """
    School-level grading scale.
    Supports Nigerian A1–F9 and generic letter/percentage systems.
    Each school has exactly one GradeConfig; created automatically on school setup.
    """

    class GradeSystem(models.TextChoices):
        NIGERIAN = 'nigerian', 'Nigerian (A1–F9)'
        LETTER = 'letter', 'Letter (A–F)'
        PERCENTAGE = 'percentage', 'Percentage'
        GPA = 'gpa', 'GPA (4.0)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='grade_config',
    )
    system = models.CharField(
        max_length=20,
        choices=GradeSystem.choices,
        default=GradeSystem.NIGERIAN,
    )
    pass_mark = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('40.00'),
        help_text='Minimum score to pass a subject (out of 100)',
    )
    # JSON list of grade bands, ordered highest → lowest.
    # Nigerian default: [{"grade":"A1","min":75,"max":100,"remark":"Excellent"},...]
    bands = models.JSONField(
        default=list,
        blank=True,
        help_text='List of grade bands: [{grade, min, max, remark, points}]',
    )
    # CA / Exam weight configuration
    ca_max_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('40.00'),
        help_text='Maximum score for Continuous Assessment',
    )
    exam_max_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('60.00'),
        help_text='Maximum score for terminal exam',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'grade config'
        verbose_name_plural = 'grade configs'

    def __str__(self):
        return f'Grade Config – {self.school.name} ({self.get_system_display()})'

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def total_max(self):
        return self.ca_max_score + self.exam_max_score

    def get_grade(self, score: Decimal) -> dict:
        """
        Return the grade band dict for a given score (0–100 percentage).
        Falls back to 'F9' / 'F' if no band matches.
        """
        if not self.bands:
            return self._default_grade(score)
        for band in self.bands:
            if Decimal(str(band['min'])) <= score <= Decimal(str(band['max'])):
                return band
        # Below lowest band
        return self.bands[-1] if self.bands else self._default_grade(score)

    @staticmethod
    def _default_grade(score: Decimal) -> dict:
        if score >= 75:
            return {'grade': 'A', 'min': 75, 'max': 100, 'remark': 'Excellent', 'points': 4.0}
        if score >= 65:
            return {'grade': 'B', 'min': 65, 'max': 74, 'remark': 'Very Good', 'points': 3.0}
        if score >= 55:
            return {'grade': 'C', 'min': 55, 'max': 64, 'remark': 'Good', 'points': 2.0}
        if score >= 45:
            return {'grade': 'D', 'min': 45, 'max': 54, 'remark': 'Pass', 'points': 1.0}
        return {'grade': 'F', 'min': 0, 'max': 44, 'remark': 'Fail', 'points': 0.0}

    @classmethod
    def nigerian_default_bands(cls):
        """Return the standard Nigerian WAEC A1–F9 grade bands."""
        return [
            {'grade': 'A1', 'min': 75, 'max': 100, 'remark': 'Excellent',  'points': 1},
            {'grade': 'B2', 'min': 70, 'max': 74,  'remark': 'Very Good',  'points': 2},
            {'grade': 'B3', 'min': 65, 'max': 69,  'remark': 'Good',       'points': 3},
            {'grade': 'C4', 'min': 60, 'max': 64,  'remark': 'Credit',     'points': 4},
            {'grade': 'C5', 'min': 55, 'max': 59,  'remark': 'Credit',     'points': 5},
            {'grade': 'C6', 'min': 50, 'max': 54,  'remark': 'Credit',     'points': 6},
            {'grade': 'D7', 'min': 45, 'max': 49,  'remark': 'Pass',       'points': 7},
            {'grade': 'E8', 'min': 40, 'max': 44,  'remark': 'Pass',       'points': 8},
            {'grade': 'F9', 'min': 0,  'max': 39,  'remark': 'Fail',       'points': 9},
        ]

    def save(self, *args, **kwargs):
        # Seed Nigerian bands on first creation if none provided
        if not self.bands and self.system == self.GradeSystem.NIGERIAN:
            self.bands = self.nigerian_default_bands()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# RESULT SHEET  (per classroom per term — the "container" for publishing)
# ─────────────────────────────────────────────────────────────────────────────

class ResultSheet(models.Model):
    """
    Represents the result sheet for a classroom in a given term.
    Controls the draft → published lifecycle.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UNDER_REVIEW = 'under_review', 'Under Review'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='result_sheets',
        db_index=True,
    )
    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.CASCADE,
        related_name='result_sheets',
        db_index=True,
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='result_sheets',
        db_index=True,
    )
    academic_session = models.ForeignKey(
        'schools.AcademicSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='result_sheets',
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_result_sheets',
    )
    published_at = models.DateTimeField(null=True, blank=True)
    next_term_begins = models.DateField(
        null=True, blank=True,
        help_text='Date next term begins (printed on report card)',
    )
    principal_remark = models.TextField(
        blank=True,
        help_text='Principal/Head teacher remark printed on all report cards',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'result sheet'
        verbose_name_plural = 'result sheets'
        unique_together = ['classroom', 'term']
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['school', 'term', 'status'],
                name='idx_rs_school_term_status',
            ),
        ]

    def __str__(self):
        return f'{self.classroom.name} – {self.term.name} [{self.status}]'

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    def publish(self, published_by):
        """Transition to published state."""
        from django.utils import timezone
        self.status = self.Status.PUBLISHED
        self.published_by = published_by
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_by', 'published_at', 'updated_at'])

    def unpublish(self):
        """Revert to draft."""
        self.status = self.Status.DRAFT
        self.published_by = None
        self.published_at = None
        self.save(update_fields=['status', 'published_by', 'published_at', 'updated_at'])


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT SCORE  (CA + Exam per subject per student per term)
# ─────────────────────────────────────────────────────────────────────────────

class StudentScore(models.Model):
    """
    Records a student's CA and exam scores for one subject in one term.
    Total score and grade are auto-calculated on save.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    result_sheet = models.ForeignKey(
        ResultSheet,
        on_delete=models.CASCADE,
        related_name='scores',
        db_index=True,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subject_scores',
        db_index=True,
    )
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='student_scores',
        db_index=True,
    )
    # ── Raw scores ────────────────────────────────────────────────────────────
    ca1_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='First CA score',
    )
    ca2_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Second CA score',
    )
    ca3_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Third CA score (optional)',
    )
    exam_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Terminal exam score',
    )
    # ── Computed fields (auto-set on save) ────────────────────────────────────
    total_ca = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Sum of all CA scores',
    )
    total_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='CA + Exam total',
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Score as percentage of total possible marks',
    )
    grade = models.CharField(max_length=5, blank=True, default='')
    grade_remark = models.CharField(max_length=50, blank=True, default='')
    grade_points = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('0.00'),
    )
    is_absent = models.BooleanField(
        default=False,
        help_text='Mark student as absent for this exam',
    )
    # ── Metadata ──────────────────────────────────────────────────────────────
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scores_entered',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'student score'
        verbose_name_plural = 'student scores'
        unique_together = ['result_sheet', 'student', 'subject']
        ordering = ['student__last_name', 'student__first_name', 'subject__name']
        indexes = [
            models.Index(
                fields=['result_sheet', 'student'],
                name='idx_score_sheet_student',
            ),
            models.Index(
                fields=['result_sheet', 'subject'],
                name='idx_score_sheet_subject',
            ),
        ]

    def __str__(self):
        return (
            f'{self.student.full_name} – {self.subject.code}: '
            f'{self.total_score} ({self.grade})'
        )

    # ── Auto-calculation ──────────────────────────────────────────────────────

    def compute_scores(self):
        """Recalculate total_ca, total_score, percentage, grade from raw scores."""
        if self.is_absent:
            self.total_ca = Decimal('0.00')
            self.total_score = Decimal('0.00')
            self.percentage = Decimal('0.00')
            self.grade = 'ABS'
            self.grade_remark = 'Absent'
            self.grade_points = Decimal('0.00')
            return

        self.total_ca = (self.ca1_score + self.ca2_score + self.ca3_score).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.total_score = (self.total_ca + self.exam_score).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Percentage relative to school's configured max
        try:
            config = self.result_sheet.school.grade_config
            total_max = config.total_max
        except Exception:
            total_max = Decimal('100.00')

        if total_max > 0:
            self.percentage = (
                (self.total_score / total_max) * 100
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            self.percentage = Decimal('0.00')

        # Clamp to 100
        self.percentage = min(self.percentage, Decimal('100.00'))

        # Grade lookup
        try:
            band = config.get_grade(self.percentage)
        except Exception:
            band = GradeConfig._default_grade(self.percentage)

        self.grade = band.get('grade', '')
        self.grade_remark = band.get('remark', '')
        self.grade_points = Decimal(str(band.get('points', 0))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def save(self, *args, **kwargs):
        self.compute_scores()
        super().save(*args, **kwargs)

    @property
    def is_pass(self):
        try:
            pass_mark = self.result_sheet.school.grade_config.pass_mark
        except Exception:
            pass_mark = Decimal('40.00')
        return self.percentage >= pass_mark


# ─────────────────────────────────────────────────────────────────────────────
# REPORT CARD  (per student per term — aggregated summary)
# ─────────────────────────────────────────────────────────────────────────────

class ReportCard(models.Model):
    """
    Aggregated term result for one student.
    Computed from StudentScore records; stores position, average, remarks.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    result_sheet = models.ForeignKey(
        ResultSheet,
        on_delete=models.CASCADE,
        related_name='report_cards',
        db_index=True,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='report_cards',
        db_index=True,
    )
    # ── Aggregated stats (auto-computed) ─────────────────────────────────────
    total_score = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0.00'),
        help_text='Sum of all subject total scores',
    )
    average_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Average percentage across all subjects',
    )
    subjects_offered = models.PositiveSmallIntegerField(default=0)
    subjects_passed = models.PositiveSmallIntegerField(default=0)
    subjects_failed = models.PositiveSmallIntegerField(default=0)
    class_position = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Position in class (1 = best)',
    )
    out_of = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Total number of students in class',
    )
    # ── Remarks ───────────────────────────────────────────────────────────────
    class_teacher_remark = models.TextField(blank=True)
    principal_remark = models.TextField(blank=True)
    # ── Attendance ────────────────────────────────────────────────────────────
    days_present = models.PositiveSmallIntegerField(default=0)
    days_absent = models.PositiveSmallIntegerField(default=0)
    days_in_term = models.PositiveSmallIntegerField(default=0)
    # ── Affective / Psychomotor domain scores (optional) ─────────────────────
    punctuality = models.CharField(max_length=20, blank=True)
    neatness = models.CharField(max_length=20, blank=True)
    attentiveness = models.CharField(max_length=20, blank=True)
    sports = models.CharField(max_length=20, blank=True)
    # ── Metadata ──────────────────────────────────────────────────────────────
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'report card'
        verbose_name_plural = 'report cards'
        unique_together = ['result_sheet', 'student']
        ordering = ['class_position', 'student__last_name']
        indexes = [
            models.Index(
                fields=['result_sheet', 'class_position'],
                name='idx_rc_sheet_position',
            ),
        ]

    def __str__(self):
        pos = f'#{self.class_position}' if self.class_position else 'unranked'
        return (
            f'{self.student.full_name} – '
            f'{self.result_sheet.term.name} – '
            f'Avg: {self.average_score}% ({pos})'
        )

    def recompute(self):
        """Recompute aggregated stats from StudentScore records."""
        scores = StudentScore.objects.filter(
            result_sheet=self.result_sheet,
            student=self.student,
            is_absent=False,
        )
        count = scores.count()
        if count == 0:
            self.subjects_offered = 0
            self.total_score = Decimal('0.00')
            self.average_score = Decimal('0.00')
            self.subjects_passed = 0
            self.subjects_failed = 0
            self.save()
            return

        try:
            pass_mark = self.result_sheet.school.grade_config.pass_mark
        except Exception:
            pass_mark = Decimal('40.00')

        agg = scores.aggregate(
            total=models.Sum('total_score'),
            avg_pct=Avg('percentage'),
            passed=Count('id', filter=Q(percentage__gte=pass_mark)),
        )
        self.subjects_offered = count
        self.total_score = (agg['total'] or Decimal('0.00')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.average_score = (agg['avg_pct'] or Decimal('0.00')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.subjects_passed = agg['passed'] or 0
        self.subjects_failed = count - self.subjects_passed
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
# SCORE ENTRY BATCH  (audit trail for bulk score uploads)
# ─────────────────────────────────────────────────────────────────────────────

class ScoreEntryBatch(models.Model):
    """
    Audit record for a batch score entry (e.g. CSV upload or bulk form submit).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    result_sheet = models.ForeignKey(
        ResultSheet,
        on_delete=models.CASCADE,
        related_name='score_batches',
        db_index=True,
    )
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='score_batches',
    )
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='score_batches',
        db_index=True,
    )
    scores_entered = models.PositiveSmallIntegerField(default=0)
    scores_updated = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'score entry batch'
        verbose_name_plural = 'score entry batches'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'Batch by {self.entered_by} – '
            f'{self.subject.code} – {self.result_sheet}'
        )
