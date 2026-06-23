"""
Models for the achievements app.
Phase 6D: Leaderboards, Badges & Achievements.

Models:
  - Badge            — definition of an achievement (name, icon, criteria)
  - StudentBadge     — awarded badge instance for a student
  - LeaderboardEntry — ranked entry for school/class/subject leaderboards
"""

import uuid
from django.conf import settings
from django.db import models

from core.models import BaseModel, SchoolScopedModel


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Badge Definitions
# ─────────────────────────────────────────────────────────────────────────────

class Badge(BaseModel):
    """
    Definition of an achievement badge.
    Platform-level badges (is_global=True) are shared across all schools.
    School-level badges are scoped to a specific school.
    """

    class BadgeType(models.TextChoices):
        # Exam performance
        FIRST_EXAM = 'first_exam', 'First Exam Completed'
        PERFECT_SCORE = 'perfect_score', 'Perfect Score'
        TOP_PERFORMER = 'top_performer', 'Top Performer'
        PASS_STREAK = 'pass_streak', 'Pass Streak'
        # Subject mastery
        MATH_GENIUS = 'math_genius', 'Math Genius'
        SCIENCE_STAR = 'science_star', 'Science Star'
        ENGLISH_MASTER = 'english_master', 'English Master'
        SUBJECT_MASTER = 'subject_master', 'Subject Master'
        # Practice & engagement
        PRACTICE_CHAMPION = 'practice_champion', 'Practice Champion'
        CONSISTENT_LEARNER = 'consistent_learner', 'Consistent Learner'
        SPEED_DEMON = 'speed_demon', 'Speed Demon'
        # Mock exams
        MOCK_MASTER = 'mock_master', 'Mock Exam Master'
        FIRST_MOCK = 'first_mock', 'First Mock Exam'
        # Improvement
        MOST_IMPROVED = 'most_improved', 'Most Improved'
        COMEBACK_KID = 'comeback_kid', 'Comeback Kid'
        # Custom (school-defined)
        CUSTOM = 'custom', 'Custom Badge'

    class Tier(models.TextChoices):
        BRONZE = 'bronze', 'Bronze'
        SILVER = 'silver', 'Silver'
        GOLD = 'gold', 'Gold'
        PLATINUM = 'platinum', 'Platinum'

    name = models.CharField(max_length=100)
    badge_type = models.CharField(
        max_length=30, choices=BadgeType.choices, db_index=True
    )
    tier = models.CharField(
        max_length=10, choices=Tier.choices, default=Tier.BRONZE
    )
    description = models.TextField()
    icon = models.CharField(
        max_length=50, default='🏅',
        help_text='Emoji or icon identifier for the badge'
    )
    # Criteria thresholds (used by badge_service)
    criteria = models.JSONField(
        default=dict, blank=True,
        help_text='e.g. {"min_score": 100, "subject_code": "MATH"}'
    )
    is_global = models.BooleanField(
        default=True,
        help_text='Global badges are available to all schools'
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='custom_badges',
        help_text='Set only for school-specific custom badges'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'badge'
        verbose_name_plural = 'badges'
        ordering = ['tier', 'name']
        indexes = [
            models.Index(fields=['badge_type', 'is_active'], name='idx_badge_type_active'),
        ]

    def __str__(self):
        return f'{self.icon} {self.name} [{self.get_tier_display()}]'


class StudentBadge(BaseModel):
    """
    An awarded badge instance for a student.
    Unique per student + badge to prevent duplicates.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='earned_badges',
        db_index=True,
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='awarded_to',
        db_index=True,
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='student_badges',
        db_index=True,
    )
    # Context: what triggered the award
    awarded_for = models.CharField(
        max_length=200, blank=True,
        help_text='Human-readable reason, e.g. "Scored 100% in MATH101 exam"'
    )
    related_object_type = models.CharField(max_length=50, blank=True, null=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    awarded_at = models.DateTimeField(auto_now_add=True)
    is_seen = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = 'student badge'
        verbose_name_plural = 'student badges'
        unique_together = ['student', 'badge']
        ordering = ['-awarded_at']
        indexes = [
            models.Index(fields=['student', 'school'], name='idx_sb_student_school'),
            models.Index(fields=['student', 'is_seen'], name='idx_sb_student_seen'),
        ]

    def __str__(self):
        return f'{self.student.full_name} earned {self.badge.name}'

    def mark_seen(self):
        self.is_seen = True
        self.save(update_fields=['is_seen', 'updated_at'])


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Leaderboard Entries
# ─────────────────────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    """
    A single ranked entry in a leaderboard snapshot.

    Leaderboard types:
      - school   : top students across the whole school for a term
      - class    : top students within a specific classroom for a term
      - subject  : top students for a specific subject for a term

    Metrics stored per entry:
      - highest_score    : best single exam score (percentage)
      - average_score    : average across all exams in scope
      - total_exams      : number of exams taken
      - total_practice   : number of practice sessions completed
      - activity_score   : composite engagement score
      - rank             : position in the leaderboard (1 = best)
    """

    class LeaderboardType(models.TextChoices):
        SCHOOL = 'school', 'School'
        CLASS = 'class', 'Class'
        SUBJECT = 'subject', 'Subject'

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='leaderboard_entries',
        db_index=True,
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leaderboard_entries',
        db_index=True,
    )
    leaderboard_type = models.CharField(
        max_length=10, choices=LeaderboardType.choices, db_index=True
    )
    # Scope (only one of these is set depending on type)
    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='leaderboard_entries',
    )
    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='leaderboard_entries',
    )
    # Student
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leaderboard_entries',
        db_index=True,
    )
    # Metrics
    rank = models.PositiveIntegerField(default=0, db_index=True)
    highest_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Best exam percentage in scope'
    )
    average_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Average exam percentage in scope'
    )
    total_exams = models.PositiveIntegerField(default=0)
    total_practice = models.PositiveIntegerField(
        default=0, help_text='Practice sessions completed'
    )
    activity_score = models.DecimalField(
        max_digits=7, decimal_places=2, default=0,
        help_text='Composite score: avg_score * 0.6 + activity_bonus * 0.4'
    )
    # Snapshot timestamp
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'leaderboard entry'
        verbose_name_plural = 'leaderboard entries'
        # One entry per student per leaderboard scope per term
        unique_together = ['school', 'term', 'leaderboard_type', 'classroom', 'subject', 'student']
        ordering = ['rank']
        indexes = [
            models.Index(
                fields=['school', 'term', 'leaderboard_type', 'rank'],
                name='idx_lb_school_term_type_rank',
            ),
            models.Index(
                fields=['school', 'leaderboard_type', 'classroom'],
                name='idx_lb_school_type_class',
            ),
            models.Index(
                fields=['school', 'leaderboard_type', 'subject'],
                name='idx_lb_school_type_subject',
            ),
        ]

    def __str__(self):
        scope = ''
        if self.classroom:
            scope = f' [{self.classroom.name}]'
        elif self.subject:
            scope = f' [{self.subject.code}]'
        return (
            f'#{self.rank} {self.student.full_name} – '
            f'{self.get_leaderboard_type_display()}{scope} '
            f'({self.average_score}%)'
        )
