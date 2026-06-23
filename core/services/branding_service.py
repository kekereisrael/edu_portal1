"""
Branding Service — manage school visual identity.

Handles logo, favicon, colours, motto, and document header/footer text.
Branding is applied to login pages, dashboards, PDFs, and certificates.
"""

import logging
from django.db import transaction

logger = logging.getLogger(__name__)


def get_or_create_branding(school):
    """Return the SchoolBranding for a school, creating it if it doesn't exist."""
    from schools.models import SchoolBranding
    branding, _ = SchoolBranding.objects.get_or_create(
        school=school,
        defaults={
            'primary_color':   school.primary_color or '#1A73E8',
            'secondary_color': school.secondary_color or '#FFFFFF',
        },
    )
    return branding


def update_branding(school, data: dict, request=None) -> object:
    """
    Update school branding fields.

    Accepted keys in data:
      logo, favicon, primary_color, secondary_color, accent_color,
      motto, tagline, report_header_text, certificate_header_text,
      report_footer_text, certificate_footer_text,
      principal_signature, stamp_image

    Also syncs primary_color / secondary_color back to School model.
    Returns the updated SchoolBranding instance.
    """
    from schools.models import SchoolBranding
    from core.services.audit_service import log_action, AuditAction

    branding = get_or_create_branding(school)

    branding_fields = [
        'logo', 'favicon', 'primary_color', 'secondary_color', 'accent_color',
        'motto', 'tagline', 'report_header_text', 'certificate_header_text',
        'report_footer_text', 'certificate_footer_text',
        'principal_signature', 'stamp_image',
    ]

    update_fields = []
    for field in branding_fields:
        if field in data:
            setattr(branding, field, data[field])
            update_fields.append(field)

    if update_fields:
        update_fields.append('updated_at')
        branding.save(update_fields=update_fields)

        # Sync colours back to School model for quick access
        school_update = []
        if 'primary_color' in data:
            school.primary_color = data['primary_color']
            school_update.append('primary_color')
        if 'secondary_color' in data:
            school.secondary_color = data['secondary_color']
            school_update.append('secondary_color')
        if 'logo' in data:
            school.logo = data['logo']
            school_update.append('logo')
        if school_update:
            school_update.append('updated_at')
            school.save(update_fields=school_update)

        log_action(
            action=AuditAction.BRANDING_UPDATED,
            school=school,
            request=request,
            target=branding,
            metadata={'updated_fields': update_fields},
        )

    return branding


def get_branding_context(school) -> dict:
    """
    Return a dict of branding values suitable for template/PDF context.
    Falls back to School model defaults if no SchoolBranding exists.
    """
    try:
        from schools.models import SchoolBranding
        branding = SchoolBranding.objects.get(school=school)
        return {
            'school_name':    school.name,
            'school_slug':    school.slug,
            'logo_url':       branding.logo.url if branding.logo else (school.logo.url if school.logo else None),
            'favicon_url':    branding.favicon.url if branding.favicon else None,
            'primary_color':  branding.primary_color,
            'secondary_color': branding.secondary_color,
            'accent_color':   branding.accent_color,
            'motto':          branding.motto or '',
            'tagline':        branding.tagline or '',
            'report_header':  branding.report_header_text or school.name,
            'cert_header':    branding.certificate_header_text or school.name,
            'report_footer':  branding.report_footer_text or '',
            'cert_footer':    branding.certificate_footer_text or '',
            'has_signature':  bool(branding.principal_signature),
            'has_stamp':      bool(branding.stamp_image),
        }
    except Exception:
        return {
            'school_name':    school.name,
            'school_slug':    school.slug,
            'logo_url':       school.logo.url if school.logo else None,
            'favicon_url':    None,
            'primary_color':  school.primary_color or '#1A73E8',
            'secondary_color': school.secondary_color or '#FFFFFF',
            'accent_color':   '#F4B400',
            'motto':          '',
            'tagline':        '',
            'report_header':  school.name,
            'cert_header':    school.name,
            'report_footer':  '',
            'cert_footer':    '',
            'has_signature':  False,
            'has_stamp':      False,
        }
