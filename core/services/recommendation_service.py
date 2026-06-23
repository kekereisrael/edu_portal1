"""
recommendation_service.py — TASK 4: Study Recommendations

Generates personalised study recommendations for a student based on:
  - TopicPerformance records (weak/average/strong classification)
  - Recent PracticeSession and MockExamSession history
  - Available materials and question banks

Returns three recommendation buckets:
  1. topics_to_revise   — weak topics ordered by lowest accuracy
  2. practice_exams     — question banks covering weak topics
  3. materials_to_study — published materials linked to weak topics
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_recommendations(student, school, subject=None, limit: int = 5) -> dict:
    """
    Return study recommendations for *student* in *school*.

    Parameters
    ----------
    student : User
    school  : School
    subject : Subject | None  — narrow to a single subject if provided
    limit   : int             — max items per bucket

    Returns
    -------
    dict with keys:
        weak_topics       list[dict]
        strong_topics     list[dict]
        topics_to_revise  list[dict]   (alias: weak topics with detail)
        practice_exams    list[dict]   (question banks to practice)
        materials_to_study list[dict]  (published materials)
        summary           dict         (counts / headline stats)
    """
    from exams.models import TopicPerformance, QuestionBank
    from materials.models import Material

    # ── 1. Fetch topic performances ──────────────────────────────────────────
    tp_qs = TopicPerformance.objects.filter(
        student=student,
        school=school,
    ).select_related('topic', 'subject').order_by('accuracy_percent')

    if subject:
        tp_qs = tp_qs.filter(subject=subject)

    weak_tps = [tp for tp in tp_qs if tp.strength_level == TopicPerformance.StrengthLevel.WEAK]
    avg_tps  = [tp for tp in tp_qs if tp.strength_level == TopicPerformance.StrengthLevel.AVERAGE]
    strong_tps = [tp for tp in tp_qs if tp.strength_level == TopicPerformance.StrengthLevel.STRONG]

    # ── 2. Topics to revise (weak first, then average) ───────────────────────
    revise_tps = (weak_tps + avg_tps)[:limit]
    topics_to_revise = [_format_topic_performance(tp) for tp in revise_tps]

    # ── 3. Practice exams (question banks covering weak topics) ──────────────
    weak_topic_ids = [tp.topic_id for tp in weak_tps]
    weak_subject_ids = list({tp.subject_id for tp in weak_tps})

    bank_qs = QuestionBank.objects.filter(
        school=school,
        is_active=True,
    ).select_related('subject', 'exam_category')

    if weak_subject_ids:
        bank_qs = bank_qs.filter(subject_id__in=weak_subject_ids)
    elif subject:
        bank_qs = bank_qs.filter(subject=subject)

    practice_exams = [_format_bank(b) for b in bank_qs[:limit]]

    # ── 4. Materials to study (published, linked to weak topics) ─────────────
    mat_qs = Material.objects.filter(
        school=school,
        is_published=True,
    ).select_related('subject', 'topic')

    if weak_topic_ids:
        # Prefer materials directly linked to weak topics
        mat_weak = mat_qs.filter(topic_id__in=weak_topic_ids).order_by('order', '-created_at')
        mat_subject = mat_qs.filter(
            subject_id__in=weak_subject_ids
        ).exclude(topic_id__in=weak_topic_ids).order_by('order', '-created_at')
        combined_ids = list(mat_weak.values_list('id', flat=True)[:limit])
        remaining = limit - len(combined_ids)
        if remaining > 0:
            combined_ids += list(mat_subject.values_list('id', flat=True)[:remaining])
        materials = mat_qs.filter(id__in=combined_ids)
    elif subject:
        materials = mat_qs.filter(subject=subject).order_by('order', '-created_at')[:limit]
    else:
        materials = mat_qs.order_by('-created_at')[:limit]

    materials_to_study = [_format_material(m) for m in materials]

    # ── 5. Summary ────────────────────────────────────────────────────────────
    total = len(list(tp_qs))
    summary = {
        'total_topics_tracked': total,
        'weak_count': len(weak_tps),
        'average_count': len(avg_tps),
        'strong_count': len(strong_tps),
        'overall_accuracy': _overall_accuracy(tp_qs),
        'needs_attention': len(weak_tps) > 0,
    }

    return {
        'weak_topics': [_format_topic_performance(tp) for tp in weak_tps[:limit]],
        'strong_topics': [_format_topic_performance(tp) for tp in strong_tps[:limit]],
        'topics_to_revise': topics_to_revise,
        'practice_exams': practice_exams,
        'materials_to_study': materials_to_study,
        'summary': summary,
    }


def get_subject_breakdown(student, school, subject) -> dict:
    """
    Detailed weak/strong breakdown for a single subject.
    Returns topic-level performance sorted by accuracy ascending.
    """
    from exams.models import TopicPerformance

    tps = TopicPerformance.objects.filter(
        student=student,
        school=school,
        subject=subject,
    ).select_related('topic').order_by('accuracy_percent')

    return {
        'subject_id': str(subject.id),
        'subject_name': subject.name,
        'subject_code': subject.code,
        'topics': [_format_topic_performance(tp) for tp in tps],
        'weak': [_format_topic_performance(tp) for tp in tps if tp.strength_level == 'weak'],
        'average': [_format_topic_performance(tp) for tp in tps if tp.strength_level == 'average'],
        'strong': [_format_topic_performance(tp) for tp in tps if tp.strength_level == 'strong'],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_topic_performance(tp) -> dict:
    return {
        'topic_id': str(tp.topic_id),
        'topic_name': tp.topic.name,
        'subject_id': str(tp.subject_id),
        'subject_name': tp.subject.name,
        'subject_code': tp.subject.code,
        'total_attempts': tp.total_attempts,
        'total_correct': tp.total_correct,
        'total_wrong': tp.total_wrong,
        'accuracy_percent': float(tp.accuracy_percent),
        'strength_level': tp.strength_level,
        'last_practiced_at': tp.last_practiced_at.isoformat() if tp.last_practiced_at else None,
    }


def _format_bank(bank) -> dict:
    return {
        'bank_id': str(bank.id),
        'name': bank.name,
        'subject_id': str(bank.subject_id),
        'subject_name': bank.subject.name,
        'subject_code': bank.subject.code,
        'exam_category': bank.exam_category.name if bank.exam_category else None,
        'question_count': bank.question_count,
        'is_shared': bank.is_shared,
    }


def _format_material(mat) -> dict:
    return {
        'material_id': str(mat.id),
        'title': mat.title,
        'material_type': mat.material_type,
        'subject_id': str(mat.subject_id),
        'subject_name': mat.subject.name,
        'topic_id': str(mat.topic_id) if mat.topic_id else None,
        'topic_name': mat.topic.name if mat.topic else None,
        'file_url': mat.file_url or (mat.file.url if mat.file else None),
        'duration_seconds': mat.duration_seconds,
    }


def _overall_accuracy(tp_qs) -> float:
    tps = list(tp_qs)
    if not tps:
        return 0.0
    total_attempts = sum(tp.total_attempts for tp in tps)
    total_correct = sum(tp.total_correct for tp in tps)
    if total_attempts == 0:
        return 0.0
    return round((total_correct / total_attempts) * 100, 1)
