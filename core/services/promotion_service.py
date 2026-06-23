"""
Promotion Service — class promotion engine for Nigerian secondary schools.

Promotion ladder:
  JSS1 → JSS2 → JSS3 → SSS1 → SSS2 → SSS3 → Alumni (graduated)

Supports:
  - Preview promotion (dry run, no DB changes)
  - Apply promotion (creates new StudentClassAssignments for next session)
  - Undo promotion (reverts to previous session assignments)
  - Promotion report (summary of promoted / graduated / skipped students)
"""

import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Promotion ladder: current level code → next level code (None = graduate)
PROMOTION_LADDER = {
    'JSS1': 'JSS2',
    'JSS2': 'JSS3',
    'JSS3': 'SSS1',
    'SSS1': 'SSS2',
    'SSS2': 'SSS3',
    'SSS3': None,   # Graduate → Alumni
}


def preview_promotion(school, from_session, to_session) -> dict:
    """
    Dry-run the promotion for a school.
    Returns a summary dict without making any DB changes.

    Returns:
        {
            "total_students": int,
            "to_promote": [{ student_id, name, from_class, to_class }],
            "to_graduate": [{ student_id, name, from_class }],
            "skipped": [{ student_id, name, reason }],
        }
    """
    from schools.models import StudentClassAssignment, ClassLevel, ClassRoom

    assignments = StudentClassAssignment.objects.filter(
        school=school,
        academic_session=from_session,
        status=StudentClassAssignment.Status.ACTIVE,
    ).select_related('student', 'classroom', 'classroom__class_level')

    to_promote  = []
    to_graduate = []
    skipped     = []

    for assignment in assignments:
        classroom   = assignment.classroom
        class_level = classroom.class_level
        student     = assignment.student

        if class_level is None:
            skipped.append({
                'student_id': str(student.id),
                'name': student.get_full_name(),
                'reason': f'Classroom "{classroom.name}" has no class level assigned.',
            })
            continue

        current_code = class_level.code
        next_code    = PROMOTION_LADDER.get(current_code)

        if next_code is None:
            # SSS3 → Graduate
            to_graduate.append({
                'student_id': str(student.id),
                'name': student.get_full_name(),
                'from_class': classroom.name,
                'from_level': current_code,
            })
        else:
            # Find a classroom at the next level in the to_session
            next_classroom = ClassRoom.objects.filter(
                school=school,
                class_level__code=next_code,
                academic_year=classroom.academic_year,
                is_active=True,
            ).first()

            to_promote.append({
                'student_id': str(student.id),
                'name': student.get_full_name(),
                'from_class': classroom.name,
                'from_level': current_code,
                'to_level': next_code,
                'to_classroom': next_classroom.name if next_classroom else f'[No {next_code} class found]',
                'to_classroom_id': str(next_classroom.id) if next_classroom else None,
            })

    return {
        'total_students': len(to_promote) + len(to_graduate) + len(skipped),
        'promote_count':  len(to_promote),
        'graduate_count': len(to_graduate),
        'skip_count':     len(skipped),
        'to_promote':     to_promote,
        'to_graduate':    to_graduate,
        'skipped':        skipped,
    }


def apply_promotion(school, from_session, to_session, promoted_by=None, request=None) -> object:
    """
    Apply the class promotion for a school.
    Creates new StudentClassAssignments for the to_session.
    Marks old assignments as GRADUATED or TRANSFERRED.
    Creates a ClassPromotion record with status=APPLIED.

    Returns the ClassPromotion instance.
    """
    from schools.models import (
        StudentClassAssignment, ClassRoom, ClassPromotion
    )
    from core.services.audit_service import log_action, AuditAction

    preview = preview_promotion(school, from_session, to_session)

    with transaction.atomic():
        promoted_ids  = []
        graduated_ids = []
        skipped_ids   = []

        # Process promotions
        for item in preview['to_promote']:
            if not item['to_classroom_id']:
                skipped_ids.append(item['student_id'])
                continue

            # Mark old assignment as transferred
            StudentClassAssignment.objects.filter(
                school=school,
                student_id=item['student_id'],
                academic_session=from_session,
                status=StudentClassAssignment.Status.ACTIVE,
            ).update(status=StudentClassAssignment.Status.TRANSFERRED)

            # Create new assignment
            StudentClassAssignment.objects.create(
                school=school,
                student_id=item['student_id'],
                classroom_id=item['to_classroom_id'],
                academic_session=to_session,
                assigned_by=promoted_by,
                status=StudentClassAssignment.Status.ACTIVE,
                notes=f'Auto-promoted from {item["from_class"]} ({from_session.name})',
            )
            promoted_ids.append(item['student_id'])

        # Process graduations
        for item in preview['to_graduate']:
            StudentClassAssignment.objects.filter(
                school=school,
                student_id=item['student_id'],
                academic_session=from_session,
                status=StudentClassAssignment.Status.ACTIVE,
            ).update(status=StudentClassAssignment.Status.GRADUATED)
            graduated_ids.append(item['student_id'])

        # Create promotion record
        promotion = ClassPromotion.objects.create(
            school=school,
            from_session=from_session,
            to_session=to_session,
            status=ClassPromotion.Status.APPLIED,
            promoted_by=promoted_by,
            applied_at=timezone.now(),
            summary={
                'promoted':  len(promoted_ids),
                'graduated': len(graduated_ids),
                'skipped':   len(skipped_ids) + len(preview['skipped']),
                'details':   preview,
            },
        )

        log_action(
            action=AuditAction.CLASS_PROMOTED,
            actor=promoted_by,
            school=school,
            target=promotion,
            request=request,
            metadata={
                'from_session': from_session.name,
                'to_session':   to_session.name,
                'promoted':     len(promoted_ids),
                'graduated':    len(graduated_ids),
            },
        )

        logger.info(
            'Class promotion applied: school=%s, %d promoted, %d graduated',
            school.name, len(promoted_ids), len(graduated_ids),
        )
        return promotion


def undo_promotion(promotion, undone_by=None, request=None) -> object:
    """
    Undo a previously applied promotion.
    Reverts new assignments and restores old ones.
    Returns the updated ClassPromotion.
    """
    from schools.models import StudentClassAssignment, ClassPromotion
    from core.services.audit_service import log_action, AuditAction

    if promotion.status != ClassPromotion.Status.APPLIED:
        raise ValueError('Only APPLIED promotions can be undone.')

    with transaction.atomic():
        details = promotion.summary.get('details', {})

        # Undo promotions: delete new assignments, restore old ones
        for item in details.get('to_promote', []):
            if not item.get('to_classroom_id'):
                continue
            # Remove the new assignment
            StudentClassAssignment.objects.filter(
                school=promotion.school,
                student_id=item['student_id'],
                academic_session=promotion.to_session,
            ).delete()
            # Restore old assignment
            StudentClassAssignment.objects.filter(
                school=promotion.school,
                student_id=item['student_id'],
                academic_session=promotion.from_session,
                status=StudentClassAssignment.Status.TRANSFERRED,
            ).update(status=StudentClassAssignment.Status.ACTIVE)

        # Undo graduations
        for item in details.get('to_graduate', []):
            StudentClassAssignment.objects.filter(
                school=promotion.school,
                student_id=item['student_id'],
                academic_session=promotion.from_session,
                status=StudentClassAssignment.Status.GRADUATED,
            ).update(status=StudentClassAssignment.Status.ACTIVE)

        promotion.status    = ClassPromotion.Status.UNDONE
        promotion.undone_at = timezone.now()
        promotion.save(update_fields=['status', 'undone_at'])

        log_action(
            action=AuditAction.CLASS_PROMOTION_UNDONE,
            actor=undone_by,
            school=promotion.school,
            target=promotion,
            request=request,
            metadata={
                'from_session': promotion.from_session.name,
                'to_session':   promotion.to_session.name,
            },
        )

        return promotion


def get_promotion_report(school) -> list[dict]:
    """Return all promotion records for a school, newest first."""
    from schools.models import ClassPromotion
    promotions = ClassPromotion.objects.filter(
        school=school
    ).select_related('from_session', 'to_session', 'promoted_by').order_by('-created_at')

    return [
        {
            'id':           str(p.id),
            'from_session': p.from_session.name,
            'to_session':   p.to_session.name,
            'status':       p.status,
            'promoted_by':  p.promoted_by.get_full_name() if p.promoted_by else 'System',
            'promoted':     p.summary.get('promoted', 0),
            'graduated':    p.summary.get('graduated', 0),
            'skipped':      p.summary.get('skipped', 0),
            'created_at':   p.created_at.isoformat(),
            'applied_at':   p.applied_at.isoformat() if p.applied_at else None,
            'undone_at':    p.undone_at.isoformat() if p.undone_at else None,
        }
        for p in promotions
    ]
