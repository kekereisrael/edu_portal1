"""
badge_service.py — TASK 2: Badge Award Logic

Evaluates which badges a student has earned after a trigger event and
awards them automatically. Idempotent — never double-awards.

Trigger events:
  - exam_attempt    : after ExamAttempt is graded
  - mock_exam       : after MockExamSession is submitted
  - practice_session: after PracticeSession is completed
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_badges_for_student(student, school, trigger: str, context: dict) -> list:
    """
    Check all active badge criteria for the student and award any newly earned badges.
    Returns list of newly awarded StudentBadge instances.
    """
    from achievements.models import Badge, StudentBadge

    active_badges = Badge.objects.filter(
        is_active=True,
    ).filter(
        # Global badges OR school-specific badges for this school
        models_Q(is_global=True) | models_Q(school=school)
    )

    newly_awarded = []
    for badge in active_badges:
        # Skip already earned
        if StudentBadge.objects.filter(student=student, badge=badge).exists():
            continue

        earned, reason = _check_criteria(badge, student, school, trigger, context)
        if earned:
            sb = StudentBadge.objects.create(
                student=student,
                badge=badge,
                school=school,
                awarded_for=reason,
                related_object_type=_get_object_type(trigger),
                related_object_id=_get_object_id(trigger, context),
            )
            newly_awarded.append(sb)

    return newly_awarded


def award_badge(student, school, badge_type: str, reason: str = '',
                related_type: str = '', related_id=None):
    """
    Directly award a specific badge type to a student.
    Safe to call multiple times — idempotent.
    """
    from achievements.models import Badge, StudentBadge

    badge = Badge.objects.filter(
        badge_type=badge_type, is_active=True
    ).filter(
        models_Q(is_global=True) | models_Q(school=school)
    ).first()

    if not badge:
        return None

    sb, created = StudentBadge.objects.get_or_create(
        student=student,
        badge=badge,
        defaults={
            'school': school,
            'awarded_for': reason,
            'related_object_type': related_type,
            'related_object_id': related_id,
        },
    )
    return sb if created else None


# ─────────────────────────────────────────────────────────────────────────────
# Criteria evaluators
# ─────────────────────────────────────────────────────────────────────────────

def _check_criteria(badge, student, school, trigger: str, context: dict):
    """
    Returns (earned: bool, reason: str).
    Dispatches to the appropriate checker based on badge_type.
    """
    from achievements.models import Badge as B

    bt = badge.badge_type
    criteria = badge.criteria or {}

    # ── Exam-based ────────────────────────────────────────────────────────────
    if bt == B.BadgeType.FIRST_EXAM:
        return _check_first_exam(student, school, trigger, context)

    if bt == B.BadgeType.PERFECT_SCORE:
        return _check_perfect_score(student, school, trigger, context, criteria)

    if bt == B.BadgeType.TOP_PERFORMER:
        return _check_top_performer(student, school, trigger, context, criteria)

    if bt == B.BadgeType.PASS_STREAK:
        return _check_pass_streak(student, school, trigger, context, criteria)

    # ── Subject mastery ───────────────────────────────────────────────────────
    if bt in (B.BadgeType.MATH_GENIUS, B.BadgeType.SCIENCE_STAR,
              B.BadgeType.ENGLISH_MASTER, B.BadgeType.SUBJECT_MASTER):
        return _check_subject_mastery(badge, student, school, trigger, context, criteria)

    # ── Practice & engagement ─────────────────────────────────────────────────
    if bt == B.BadgeType.PRACTICE_CHAMPION:
        return _check_practice_champion(student, school, trigger, context, criteria)

    if bt == B.BadgeType.CONSISTENT_LEARNER:
        return _check_consistent_learner(student, school, trigger, context, criteria)

    if bt == B.BadgeType.SPEED_DEMON:
        return _check_speed_demon(student, school, trigger, context, criteria)

    # ── Mock exams ────────────────────────────────────────────────────────────
    if bt == B.BadgeType.FIRST_MOCK:
        return _check_first_mock(student, school, trigger, context)

    if bt == B.BadgeType.MOCK_MASTER:
        return _check_mock_master(student, school, trigger, context, criteria)

    # ── Improvement ───────────────────────────────────────────────────────────
    if bt == B.BadgeType.MOST_IMPROVED:
        return _check_most_improved(student, school, trigger, context, criteria)

    if bt == B.BadgeType.COMEBACK_KID:
        return _check_comeback_kid(student, school, trigger, context, criteria)

    return False, ''


# ── Individual checkers ───────────────────────────────────────────────────────

def _check_first_exam(student, school, trigger, context):
    if trigger != 'exam_attempt':
        return False, ''
    from exams.models import ExamAttempt
    count = ExamAttempt.objects.filter(
        student=student,
        exam__school=school,
        status__in=['graded', 'submitted'],
    ).count()
    if count >= 1:
        exam = context.get('exam')
        return True, f'Completed your first exam: {exam.title if exam else ""}'
    return False, ''


def _check_perfect_score(student, school, trigger, context, criteria):
    if trigger not in ('exam_attempt', 'mock_exam'):
        return False, ''
    pct = context.get('percentage', 0)
    min_score = criteria.get('min_score', 100)
    if pct >= min_score:
        exam = context.get('exam')
        title = exam.title if exam else 'mock exam'
        return True, f'Scored {pct}% in {title}'
    return False, ''


def _check_top_performer(student, school, trigger, context, criteria):
    if trigger != 'exam_attempt':
        return False, ''
    pct = context.get('percentage', 0)
    threshold = criteria.get('min_score', 90)
    if pct >= threshold:
        exam = context.get('exam')
        return True, f'Scored {pct}% (top performer threshold: {threshold}%) in {exam.title if exam else ""}'
    return False, ''


def _check_pass_streak(student, school, trigger, context, criteria):
    if trigger != 'exam_attempt':
        return False, ''
    from exams.models import ExamAttempt
    streak_needed = criteria.get('streak', 3)
    recent = list(
        ExamAttempt.objects.filter(
            student=student,
            exam__school=school,
            status='graded',
        ).order_by('-started_at').values_list('passed', flat=True)[:streak_needed]
    )
    if len(recent) >= streak_needed and all(recent):
        return True, f'Passed {streak_needed} exams in a row'
    return False, ''


def _check_subject_mastery(badge, student, school, trigger, context, criteria):
    if trigger != 'exam_attempt':
        return False, ''
    from exams.models import TopicPerformance
    subject_code = criteria.get('subject_code', '')
    min_accuracy = criteria.get('min_accuracy', 75)
    qs = TopicPerformance.objects.filter(
        student=student, school=school,
    )
    if subject_code:
        qs = qs.filter(subject__code__iexact=subject_code)
    if not qs.exists():
        return False, ''
    avg = sum(float(tp.accuracy_percent) for tp in qs) / qs.count()
    if avg >= min_accuracy:
        subj = qs.first().subject
        return True, f'Achieved {avg:.1f}% average accuracy in {subj.name}'
    return False, ''


def _check_practice_champion(student, school, trigger, context, criteria):
    if trigger != 'practice_session':
        return False, ''
    from exams.models import PracticeSession
    needed = criteria.get('sessions', 10)
    count = PracticeSession.objects.filter(
        student=student,
        bank__school=school,
        status='completed',
    ).count()
    if count >= needed:
        return True, f'Completed {count} practice sessions'
    return False, ''


def _check_consistent_learner(student, school, trigger, context, criteria):
    """Award if student has activity on 7 distinct days in the last 14 days."""
    from django.utils import timezone
    from datetime import timedelta
    from exams.models import PracticeSession, ExamAttempt
    days_needed = criteria.get('days', 7)
    window = criteria.get('window_days', 14)
    since = timezone.now() - timedelta(days=window)

    practice_days = set(
        PracticeSession.objects.filter(
            student=student, bank__school=school, created_at__gte=since
        ).values_list('created_at__date', flat=True)
    )
    exam_days = set(
        ExamAttempt.objects.filter(
            student=student, exam__school=school, started_at__gte=since
        ).values_list('started_at__date', flat=True)
    )
    active_days = practice_days | exam_days
    if len(active_days) >= days_needed:
        return True, f'Active on {len(active_days)} days in the last {window} days'
    return False, ''


def _check_speed_demon(student, school, trigger, context, criteria):
    """Award if student completes an exam in under X% of the allotted time with a passing score."""
    if trigger != 'exam_attempt':
        return False, ''
    attempt = context.get('attempt')
    if not attempt:
        return False, ''
    pct = context.get('percentage', 0)
    min_pass = criteria.get('min_score', 70)
    speed_threshold = criteria.get('speed_pct', 50)  # completed in <50% of time
    if pct < min_pass:
        return False, ''
    allotted = attempt.exam.duration_minutes * 60
    taken = attempt.time_taken_seconds or allotted
    if allotted > 0 and (taken / allotted * 100) <= speed_threshold:
        return True, f'Completed exam in {taken // 60}m with {pct}%'
    return False, ''


def _check_first_mock(student, school, trigger, context):
    if trigger != 'mock_exam':
        return False, ''
    from exams.models import MockExamSession
    count = MockExamSession.objects.filter(
        student=student,
        bank__school=school,
        status__in=['submitted', 'timed_out'],
    ).count()
    if count >= 1:
        return True, 'Completed your first mock exam'
    return False, ''


def _check_mock_master(student, school, trigger, context, criteria):
    if trigger != 'mock_exam':
        return False, ''
    from exams.models import MockExamSession
    needed = criteria.get('sessions', 5)
    min_score = criteria.get('min_score', 70)
    count = MockExamSession.objects.filter(
        student=student,
        bank__school=school,
        status='submitted',
        percentage__gte=min_score,
    ).count()
    if count >= needed:
        return True, f'Passed {count} mock exams with ≥{min_score}%'
    return False, ''


def _check_most_improved(student, school, trigger, context, criteria):
    """Award if student's last 3 exam scores show consistent improvement."""
    if trigger != 'exam_attempt':
        return False, ''
    from exams.models import ExamAttempt
    recent = list(
        ExamAttempt.objects.filter(
            student=student,
            exam__school=school,
            status='graded',
            percentage__isnull=False,
        ).order_by('-started_at').values_list('percentage', flat=True)[:3]
    )
    if len(recent) < 3:
        return False, ''
    # recent[0] is newest — check ascending order (newest > previous)
    if recent[0] > recent[1] > recent[2]:
        return True, f'Improved scores: {recent[2]}% → {recent[1]}% → {recent[0]}%'
    return False, ''


def _check_comeback_kid(student, school, trigger, context, criteria):
    """Award if student failed an exam then passed the next attempt."""
    if trigger != 'exam_attempt':
        return False, ''
    attempt = context.get('attempt')
    if not attempt or not attempt.passed:
        return False, ''
    from exams.models import ExamAttempt
    prev = ExamAttempt.objects.filter(
        student=student,
        exam=attempt.exam,
        status='graded',
        started_at__lt=attempt.started_at,
    ).order_by('-started_at').first()
    if prev and not prev.passed:
        return True, f'Failed then passed {attempt.exam.title}'
    return False, ''


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_object_type(trigger: str) -> str:
    mapping = {
        'exam_attempt': 'examattempt',
        'mock_exam': 'mockexamsession',
        'practice_session': 'practicesession',
    }
    return mapping.get(trigger, '')


def _get_object_id(trigger: str, context: dict):
    if trigger == 'exam_attempt':
        obj = context.get('attempt')
    elif trigger == 'mock_exam':
        obj = context.get('session')
    elif trigger == 'practice_session':
        obj = context.get('session')
    else:
        return None
    return obj.id if obj else None


# Lazy import to avoid circular imports at module load time
def models_Q(*args, **kwargs):
    from django.db.models import Q
    return Q(*args, **kwargs)
