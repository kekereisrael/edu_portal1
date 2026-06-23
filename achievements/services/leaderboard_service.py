"""
leaderboard_service.py — TASK 1: Leaderboard Calculation

Computes and persists LeaderboardEntry records for:
  - School leaderboard  : top students across the whole school for a term
  - Class leaderboard   : top students within a specific classroom
  - Subject leaderboard : top students for a specific subject

Metrics per entry:
  - highest_score   : best single exam percentage
  - average_score   : average exam percentage
  - total_exams     : exams taken
  - total_practice  : practice sessions completed
  - activity_score  : composite (avg_score * 0.6 + activity_bonus * 0.4)

Call rebuild_leaderboard() after each exam submission or via Celery beat.
"""

from __future__ import annotations
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def rebuild_school_leaderboard(school, term=None, limit: int = 50) -> list:
    """Rebuild the school-wide leaderboard. Returns list of LeaderboardEntry."""
    from achievements.models import LeaderboardEntry
    entries = _compute_entries(
        school=school, term=term,
        leaderboard_type=LeaderboardEntry.LeaderboardType.SCHOOL,
        limit=limit,
    )
    return _persist_entries(entries, school, term, LeaderboardEntry.LeaderboardType.SCHOOL)


def rebuild_class_leaderboard(school, classroom, term=None, limit: int = 50) -> list:
    """Rebuild the leaderboard for a specific classroom."""
    from achievements.models import LeaderboardEntry
    entries = _compute_entries(
        school=school, term=term,
        leaderboard_type=LeaderboardEntry.LeaderboardType.CLASS,
        classroom=classroom,
        limit=limit,
    )
    return _persist_entries(
        entries, school, term,
        LeaderboardEntry.LeaderboardType.CLASS,
        classroom=classroom,
    )


def rebuild_subject_leaderboard(school, subject, term=None, limit: int = 50) -> list:
    """Rebuild the leaderboard for a specific subject."""
    from achievements.models import LeaderboardEntry
    entries = _compute_entries(
        school=school, term=term,
        leaderboard_type=LeaderboardEntry.LeaderboardType.SUBJECT,
        subject=subject,
        limit=limit,
    )
    return _persist_entries(
        entries, school, term,
        LeaderboardEntry.LeaderboardType.SUBJECT,
        subject=subject,
    )


def get_school_leaderboard(school, term=None, limit: int = 20) -> list:
    """Return current school leaderboard entries (read-only)."""
    from achievements.models import LeaderboardEntry
    qs = LeaderboardEntry.objects.filter(
        school=school,
        leaderboard_type=LeaderboardEntry.LeaderboardType.SCHOOL,
        classroom__isnull=True,
        subject__isnull=True,
    ).select_related('student')
    if term:
        qs = qs.filter(term=term)
    return list(qs.order_by('rank')[:limit])


def get_class_leaderboard(school, classroom, term=None, limit: int = 50) -> list:
    """Return current class leaderboard entries."""
    from achievements.models import LeaderboardEntry
    qs = LeaderboardEntry.objects.filter(
        school=school,
        leaderboard_type=LeaderboardEntry.LeaderboardType.CLASS,
        classroom=classroom,
    ).select_related('student')
    if term:
        qs = qs.filter(term=term)
    return list(qs.order_by('rank')[:limit])


def get_subject_leaderboard(school, subject, term=None, limit: int = 50) -> list:
    """Return current subject leaderboard entries."""
    from achievements.models import LeaderboardEntry
    qs = LeaderboardEntry.objects.filter(
        school=school,
        leaderboard_type=LeaderboardEntry.LeaderboardType.SUBJECT,
        subject=subject,
    ).select_related('student')
    if term:
        qs = qs.filter(term=term)
    return list(qs.order_by('rank')[:limit])


def get_student_rank(school, student, term=None, leaderboard_type='school',
                     classroom=None, subject=None) -> dict:
    """Return a student's rank and stats in a specific leaderboard."""
    from achievements.models import LeaderboardEntry
    qs = LeaderboardEntry.objects.filter(
        school=school,
        student=student,
        leaderboard_type=leaderboard_type,
    )
    if term:
        qs = qs.filter(term=term)
    if classroom:
        qs = qs.filter(classroom=classroom)
    if subject:
        qs = qs.filter(subject=subject)
    entry = qs.first()
    if not entry:
        return {'rank': None, 'average_score': 0, 'highest_score': 0, 'total_exams': 0}
    return {
        'rank': entry.rank,
        'average_score': float(entry.average_score),
        'highest_score': float(entry.highest_score),
        'total_exams': entry.total_exams,
        'total_practice': entry.total_practice,
        'activity_score': float(entry.activity_score),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_entries(school, term, leaderboard_type, classroom=None,
                     subject=None, limit: int = 50) -> list:
    """
    Compute raw leaderboard data from ExamAttempt and PracticeSession records.
    Returns list of dicts sorted by activity_score desc.
    """
    from django.db.models import Avg, Max, Count, Q
    from exams.models import ExamAttempt, PracticeSession
    from accounts.models import User

    # Base attempt filter
    attempt_filter = Q(
        exam__school=school,
        status__in=['graded', 'submitted'],
        percentage__isnull=False,
    )
    if term:
        attempt_filter &= Q(exam__term=term)
    if subject:
        attempt_filter &= Q(exam__subject=subject)
    if classroom:
        # Filter by students enrolled in this classroom
        from subjects.models import Enrollment
        enrolled_ids = Enrollment.objects.filter(
            classroom=classroom,
            status='active',
        ).values_list('student_id', flat=True)
        attempt_filter &= Q(student_id__in=enrolled_ids)

    # Aggregate per student
    student_stats = (
        ExamAttempt.objects.filter(attempt_filter)
        .values('student_id')
        .annotate(
            avg_score=Avg('percentage'),
            max_score=Max('percentage'),
            exam_count=Count('id'),
        )
    )

    # Practice session counts
    practice_filter = Q(bank__school=school, status='completed')
    if classroom:
        practice_filter &= Q(student_id__in=enrolled_ids)

    practice_counts = {
        row['student_id']: row['count']
        for row in PracticeSession.objects.filter(practice_filter)
        .values('student_id')
        .annotate(count=Count('id'))
    }

    # Build scored list
    scored = []
    for row in student_stats:
        sid = row['student_id']
        avg = float(row['avg_score'] or 0)
        high = float(row['max_score'] or 0)
        exams = row['exam_count']
        practice = practice_counts.get(sid, 0)
        # Activity bonus: 1 point per exam + 0.5 per practice session, capped at 20
        activity_bonus = min(exams * 1.0 + practice * 0.5, 20)
        activity_score = round(avg * 0.6 + activity_bonus * 2, 2)  # scale bonus to 0-40
        scored.append({
            'student_id': sid,
            'average_score': round(avg, 2),
            'highest_score': round(high, 2),
            'total_exams': exams,
            'total_practice': practice,
            'activity_score': activity_score,
        })

    # Sort by activity_score desc, then avg_score desc
    scored.sort(key=lambda x: (x['activity_score'], x['average_score']), reverse=True)
    return scored[:limit]


def _persist_entries(entries: list, school, term, leaderboard_type,
                     classroom=None, subject=None) -> list:
    """
    Upsert LeaderboardEntry records from computed data.
    Returns list of saved LeaderboardEntry instances.
    """
    from achievements.models import LeaderboardEntry

    saved = []
    for rank, data in enumerate(entries, start=1):
        entry, _ = LeaderboardEntry.objects.update_or_create(
            school=school,
            term=term,
            leaderboard_type=leaderboard_type,
            classroom=classroom,
            subject=subject,
            student_id=data['student_id'],
            defaults={
                'rank': rank,
                'average_score': Decimal(str(data['average_score'])),
                'highest_score': Decimal(str(data['highest_score'])),
                'total_exams': data['total_exams'],
                'total_practice': data['total_practice'],
                'activity_score': Decimal(str(data['activity_score'])),
            },
        )
        saved.append(entry)
    return saved
