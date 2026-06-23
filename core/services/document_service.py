"""
Document Service — generate school documents as structured data for PDF rendering.

Documents:
  - Student ID Card
  - Result Sheet (per student per term)
  - Report Card (per student per session)
  - Examination Slip
  - Certificate (completion / graduation)

Returns structured dicts that the frontend or a PDF renderer can consume.
ReportLab PDF generation is available when the package is installed.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def _get_student_profile(student_user, school):
    try:
        from accounts.models import StudentProfile
        return StudentProfile.objects.get(user=student_user, school=school)
    except Exception:
        return None


def _get_current_assignment(student_user, school):
    try:
        from schools.models import StudentClassAssignment
        return StudentClassAssignment.objects.filter(
            school=school,
            student=student_user,
            status=StudentClassAssignment.Status.ACTIVE,
        ).select_related('classroom', 'academic_session').first()
    except Exception:
        return None


def generate_student_id_card_data(student_user, school) -> dict:
    """Return structured data for a student ID card."""
    from core.services.branding_service import get_branding_context

    branding   = get_branding_context(school)
    profile    = _get_student_profile(student_user, school)
    assignment = _get_current_assignment(student_user, school)

    return {
        'document_type': 'student_id_card',
        'school': {
            'name':          school.name,
            'logo_url':      branding['logo_url'],
            'primary_color': branding['primary_color'],
            'motto':         branding['motto'],
        },
        'student': {
            'id':               str(student_user.id),
            'full_name':        student_user.get_full_name(),
            'email':            student_user.email,
            'admission_number': profile.admission_number if profile else '',
            'gender':           profile.gender if profile else '',
            'date_of_birth':    profile.date_of_birth.isoformat() if profile and profile.date_of_birth else '',
            'photo_url':        profile.profile_picture.url if profile and profile.profile_picture else None,
            'current_class':    assignment.classroom.name if assignment else '',
            'session':          assignment.academic_session.name if assignment else '',
        },
        'generated_at': _now_iso(),
    }


def generate_result_sheet_data(student_user, school, term=None, session=None) -> dict:
    """Return structured data for a student result sheet."""
    from core.services.branding_service import get_branding_context

    branding   = get_branding_context(school)
    profile    = _get_student_profile(student_user, school)
    assignment = _get_current_assignment(student_user, school)

    results = []
    try:
        from results.models import Result
        qs = Result.objects.filter(school=school, student=student_user)
        if term:
            qs = qs.filter(term=term)
        if session:
            qs = qs.filter(academic_session=session)
        for r in qs.select_related('subject'):
            results.append({
                'subject':    r.subject.name if hasattr(r, 'subject') and r.subject else '',
                'ca_score':   getattr(r, 'ca_score', None),
                'exam_score': getattr(r, 'exam_score', None),
                'total':      getattr(r, 'total_score', None),
                'grade':      getattr(r, 'grade', ''),
                'remark':     getattr(r, 'remark', ''),
            })
    except Exception:
        pass

    return {
        'document_type': 'result_sheet',
        'school': {
            'name':          school.name,
            'logo_url':      branding['logo_url'],
            'primary_color': branding['primary_color'],
            'header_text':   branding['report_header'],
            'footer_text':   branding['report_footer'],
        },
        'student': {
            'full_name':        student_user.get_full_name(),
            'admission_number': profile.admission_number if profile else '',
            'current_class':    assignment.classroom.name if assignment else '',
            'session':          assignment.academic_session.name if assignment else '',
            'term':             term.name if term else '',
        },
        'results':      results,
        'generated_at': _now_iso(),
    }


def generate_report_card_data(student_user, school, session=None) -> dict:
    """Return structured data for a full session report card."""
    data = generate_result_sheet_data(student_user, school, session=session)
    data['document_type'] = 'report_card'
    data['comments'] = {'class_teacher': '', 'principal': ''}
    return data


def generate_exam_slip_data(student_user, school, exam) -> dict:
    """Return structured data for an examination slip."""
    from core.services.branding_service import get_branding_context

    branding   = get_branding_context(school)
    profile    = _get_student_profile(student_user, school)
    assignment = _get_current_assignment(student_user, school)

    return {
        'document_type': 'exam_slip',
        'school': {
            'name':          school.name,
            'logo_url':      branding['logo_url'],
            'primary_color': branding['primary_color'],
        },
        'student': {
            'full_name':        student_user.get_full_name(),
            'admission_number': profile.admission_number if profile else '',
            'current_class':    assignment.classroom.name if assignment else '',
            'photo_url':        profile.profile_picture.url if profile and profile.profile_picture else None,
        },
        'exam': {
            'id':               str(exam.pk),
            'title':            exam.title,
            'subject':          str(exam.subject) if hasattr(exam, 'subject') else '',
            'date':             str(getattr(exam, 'start_date', '')),
            'duration_minutes': getattr(exam, 'duration_minutes', None),
            'venue':            getattr(exam, 'venue', ''),
        },
        'generated_at': _now_iso(),
    }


def generate_certificate_data(student_user, school, certificate_type: str = 'completion') -> dict:
    """Return structured data for a completion/graduation certificate."""
    from core.services.branding_service import get_branding_context

    branding = get_branding_context(school)
    profile  = _get_student_profile(student_user, school)

    return {
        'document_type':    'certificate',
        'certificate_type': certificate_type,
        'school': {
            'name':           school.name,
            'logo_url':       branding['logo_url'],
            'primary_color':  branding['primary_color'],
            'header_text':    branding['cert_header'],
            'footer_text':    branding['cert_footer'],
            'has_signature':  branding['has_signature'],
            'has_stamp':      branding['has_stamp'],
        },
        'student': {
            'full_name':        student_user.get_full_name(),
            'admission_number': profile.admission_number if profile else '',
            'gender':           profile.gender if profile else '',
        },
        'generated_at': _now_iso(),
    }


def generate_pdf_bytes(document_data: dict) -> bytes | None:
    """
    Attempt to render document_data as a PDF using ReportLab.
    Returns bytes on success, None if ReportLab is not installed.

    For production use, integrate a proper template-based PDF renderer
    (WeasyPrint, xhtml2pdf, or a headless Chrome solution).
    """
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
        from io import BytesIO

        buffer = BytesIO()
        c = rl_canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        doc_type = document_data.get('document_type', 'document')
        school   = document_data.get('school', {})
        student  = document_data.get('student', {})

        # Simple text-based layout (replace with proper template in production)
        c.setFont('Helvetica-Bold', 16)
        c.drawCentredString(width / 2, height - 60, school.get('name', ''))

        c.setFont('Helvetica', 12)
        c.drawCentredString(width / 2, height - 85, school.get('header_text', doc_type.replace('_', ' ').title()))

        c.setFont('Helvetica', 11)
        y = height - 140
        for key, value in student.items():
            if value:
                c.drawString(72, y, f'{key.replace("_", " ").title()}: {value}')
                y -= 20

        if doc_type == 'result_sheet':
            y -= 20
            c.setFont('Helvetica-Bold', 11)
            c.drawString(72, y, 'Subject')
            c.drawString(250, y, 'CA')
            c.drawString(310, y, 'Exam')
            c.drawString(370, y, 'Total')
            c.drawString(430, y, 'Grade')
            y -= 15
            c.setFont('Helvetica', 10)
            for result in document_data.get('results', []):
                c.drawString(72, y, str(result.get('subject', '')))
                c.drawString(250, y, str(result.get('ca_score', '') or ''))
                c.drawString(310, y, str(result.get('exam_score', '') or ''))
                c.drawString(370, y, str(result.get('total', '') or ''))
                c.drawString(430, y, str(result.get('grade', '')))
                y -= 15
                if y < 72:
                    c.showPage()
                    y = height - 72

        c.setFont('Helvetica', 8)
        c.drawCentredString(width / 2, 40, f'Generated: {document_data.get("generated_at", "")}')
        c.save()

        return buffer.getvalue()

    except ImportError:
        logger.info('ReportLab not installed — PDF generation unavailable.')
        return None
    except Exception as exc:
        logger.error('PDF generation failed: %s', exc, exc_info=True)
        return None
