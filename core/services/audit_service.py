"""
Audit Service — centralised audit logging for all school actions.

Usage:
    from core.services.audit_service import log_action, AuditAction

    log_action(
        action=AuditAction.STUDENT_CREATED,
        actor=request.user,
        school=request.school,
        target=student_user,
        request=request,
        metadata={'admission_number': '2024/001'},
    )
"""

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


# Re-export the Action choices for convenience
def _get_action_class():
    from schools.models import AuditLog
    return AuditLog.Action


class AuditAction:
    """Namespace for audit action constants (mirrors AuditLog.Action)."""
    STUDENT_CREATED   = 'student_created'
    STUDENT_UPDATED   = 'student_updated'
    STUDENT_DELETED   = 'student_deleted'
    TEACHER_CREATED   = 'teacher_created'
    TEACHER_UPDATED   = 'teacher_updated'
    TEACHER_DELETED   = 'teacher_deleted'
    PARENT_CREATED    = 'parent_created'
    PARENT_UPDATED    = 'parent_updated'
    PARENT_DELETED    = 'parent_deleted'
    PARENT_LINKED     = 'parent_linked'
    PARENT_UNLINKED   = 'parent_unlinked'
    EXAM_CREATED      = 'exam_created'
    EXAM_PUBLISHED    = 'exam_published'
    EXAM_DELETED      = 'exam_deleted'
    RESULT_MODIFIED   = 'result_modified'
    RESULT_PUBLISHED  = 'result_published'
    CLASS_PROMOTED    = 'class_promoted'
    CLASS_PROMOTION_UNDONE = 'class_promotion_undone'
    SCHOOL_SETTINGS_UPDATED = 'school_settings_updated'
    BRANDING_UPDATED  = 'branding_updated'
    MEMBER_ADDED      = 'member_added'
    MEMBER_REMOVED    = 'member_removed'
    BULK_IMPORT       = 'bulk_import'
    DOCUMENT_GENERATED = 'document_generated'
    LOGIN             = 'login'
    LOGOUT            = 'logout'
    PASSWORD_CHANGED  = 'password_changed'


def log_action(
    *,
    action: str,
    actor=None,
    school=None,
    target=None,
    target_type: str = None,
    target_id: str = None,
    target_repr: str = None,
    metadata: dict = None,
    request=None,
    ip_address: str = None,
    user_agent: str = None,
):
    """
    Create an AuditLog entry.

    Args:
        action:       One of AuditAction.* constants
        actor:        User who performed the action (or None for system)
        school:       School context (or None for platform-level)
        target:       The affected model instance (optional)
        target_type:  Override model name (auto-detected from target if not given)
        target_id:    Override target PK (auto-detected from target if not given)
        target_repr:  Human-readable description of the target
        metadata:     Extra context dict (before/after values, counts, etc.)
        request:      DRF/Django request (used to extract IP + user agent)
        ip_address:   Override IP address
        user_agent:   Override user agent string

    Returns:
        AuditLog instance (or None on failure — audit must never crash the app)
    """
    try:
        from schools.models import AuditLog

        # Resolve actor from request if not provided
        if actor is None and request is not None:
            actor = getattr(request, 'user', None)
            if actor and not actor.is_authenticated:
                actor = None

        # Resolve school from request if not provided
        if school is None and request is not None:
            school = getattr(request, 'school', None)

        # Resolve IP
        if ip_address is None and request is not None:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = (
                x_forwarded_for.split(',')[0].strip()
                if x_forwarded_for
                else request.META.get('REMOTE_ADDR')
            )

        # Resolve user agent
        if user_agent is None and request is not None:
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Resolve target fields from the object
        if target is not None:
            if target_type is None:
                target_type = type(target).__name__
            if target_id is None:
                target_id = str(getattr(target, 'pk', '') or '')
            if target_repr is None:
                target_repr = str(target)[:255]

        return AuditLog.objects.create(
            school=school,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_repr=target_repr,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=(user_agent or '')[:500],
        )

    except Exception as exc:
        # Audit logging must NEVER crash the application
        logger.error('AuditLog creation failed: %s', exc, exc_info=True)
        return None


def get_school_audit_logs(school, *, action=None, actor=None, limit=50, offset=0):
    """
    Return a queryset of audit logs for a school, newest first.
    Optionally filter by action type or actor.
    """
    from schools.models import AuditLog
    qs = AuditLog.objects.filter(school=school).select_related('actor')
    if action:
        qs = qs.filter(action=action)
    if actor:
        qs = qs.filter(actor=actor)
    return qs.order_by('-created_at')[offset:offset + limit]


def get_recent_activity(school, limit=20) -> list[dict]:
    """
    Return a list of recent audit log entries formatted for the dashboard.
    """
    from schools.models import AuditLog
    logs = AuditLog.objects.filter(
        school=school
    ).select_related('actor').order_by('-created_at')[:limit]

    return [
        {
            'id': str(log.id),
            'action': log.action,
            'action_display': log.get_action_display(),
            'actor': log.actor.get_full_name() if log.actor else 'System',
            'actor_email': log.actor.email if log.actor else None,
            'target_type': log.target_type,
            'target_repr': log.target_repr,
            'metadata': log.metadata,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat(),
        }
        for log in logs
    ]
