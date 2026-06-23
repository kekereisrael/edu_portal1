"""
Views for serving the frontend templates.
Views are kept thin - they only call service layer and pass context to templates.
Role-based redirection: Student → student_dashboard, Teacher → teacher_dashboard, Admin → admin_dashboard
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from accounts.models import User


def get_role_redirect_url(user):
    """Get the redirect URL based on user role."""
    if user.role in (User.Role.PLATFORM_ADMIN, User.Role.SCHOOL_ADMIN):
        return '/admin-dashboard/'
    elif user.role == User.Role.TEACHER:
        return '/teacher/dashboard/'
    else:
        return '/student/dashboard/'


def dashboard_view(request):
    """Root dashboard — redirect authenticated users to their role-based dashboard."""
    if request.user.is_authenticated:
        return redirect(get_role_redirect_url(request.user))
    # Unauthenticated users see the login page
    return redirect('/auth/login/')


@login_required(login_url='/auth/login/')
def student_dashboard_view(request):
    """Student dashboard view."""
    user = request.user

    # Redirect non-students away
    if user.role not in (User.Role.STUDENT, User.Role.PARENT):
        return redirect(get_role_redirect_url(user))

    try:
        from core.services.dashboard_service import get_student_dashboard_data
        raw = get_student_dashboard_data(user)
        # Compute additional stats
        recent_scores = raw.get('recent_scores', [])
        completed = len([s for s in recent_scores if s.get('percentage', 0) > 0])
        passed = len([s for s in recent_scores if s.get('passed', False)])
        pass_rate = round((passed / completed * 100), 1) if completed > 0 else 0
        avg = raw.get('average_score', 0)
        data = {
            'total_exams': raw.get('total_exams', 0),
            'completed_exams': completed,
            'average_score': f"{avg}%" if avg else "0%",
            'pass_rate': f"{pass_rate}%",
            'recent_scores': recent_scores,
            'upcoming_exams': raw.get('upcoming_exams', []),
            'in_progress_count': raw.get('in_progress_count', 0),
            'active_page': 'dashboard',
        }
    except Exception:
        data = {
            'total_exams': 0,
            'completed_exams': 0,
            'average_score': '0%',
            'pass_rate': '0%',
            'recent_scores': [],
            'upcoming_exams': [],
            'in_progress_count': 0,
            'active_page': 'dashboard',
        }

    try:
        from core.services.notification_service import get_unread_count
        data['unread_notifications'] = get_unread_count(user)
    except Exception:
        data['unread_notifications'] = 0

    data['active_page'] = 'dashboard'
    return render(request, 'dashboards/student_dashboard.html', data)


@login_required(login_url='/auth/login/')
def teacher_dashboard_view(request):
    """Teacher dashboard view."""
    user = request.user

    # Redirect non-teachers away
    if user.role not in (User.Role.TEACHER, User.Role.SCHOOL_ADMIN, User.Role.PLATFORM_ADMIN):
        return redirect(get_role_redirect_url(user))

    try:
        from core.services.dashboard_service import get_teacher_dashboard_data
        raw = get_teacher_dashboard_data(user)
        # Map service keys to template-friendly keys
        data = {
            'subjects_managed': raw.get('subjects_managed', 0),
            'materials_uploaded': raw.get('materials_uploaded', 0),
            'exams_created': raw.get('total_exams_created', 0),
            'students_reached': raw.get('students_reached', 0),
            'recent_exams': raw.get('recent_exams', []),
            'recent_submissions': raw.get('pending_grading', []),
            'active_page': 'dashboard',
        }
    except Exception:
        data = {
            'subjects_managed': 0,
            'materials_uploaded': 0,
            'exams_created': 0,
            'students_reached': 0,
            'recent_exams': [],
            'recent_submissions': [],
            'active_page': 'dashboard',
        }

    try:
        from core.services.notification_service import get_unread_count
        data['unread_notifications'] = get_unread_count(user)
    except Exception:
        data['unread_notifications'] = 0

    data['active_page'] = 'dashboard'
    return render(request, 'dashboards/teacher_dashboard.html', data)


@login_required(login_url='/auth/login/')
def admin_dashboard_view(request):
    """Admin dashboard view."""
    user = request.user

    if user.role not in (User.Role.PLATFORM_ADMIN, User.Role.SCHOOL_ADMIN):
        return redirect(get_role_redirect_url(user))

    data = {
        'active_page': 'dashboard',
        'unread_notifications': 0,
    }

    try:
        from core.services.notification_service import get_unread_count
        data['unread_notifications'] = get_unread_count(user)
    except Exception:
        pass

    return render(request, 'dashboards/admin_dashboard.html', data)


@login_required(login_url='/auth/login/')
def exam_page_view(request):
    """Render the exam taking page with safety guards."""
    from exams.models import Exam
    from core.services.exam_service import (
        get_exam_questions_for_student,
        validate_exam_availability,
        has_questions,
    )

    exam_id = request.GET.get('exam_id')

    if not exam_id:
        context = {
            'active_page': 'exams',
            'current_question': 1,
            'total_questions': 14,
            'lab_current': 0,
            'lab_total': 2,
            'exam_duration_seconds': 28767,
        }
        return render(request, 'exam_page.html', context)

    try:
        exam = Exam.objects.get(id=exam_id)
    except (Exam.DoesNotExist, ValueError, Exception):
        return render(request, 'no_exam.html', {
            'active_page': 'exams',
            'message': 'The requested exam could not be found.',
        })

    if not has_questions(exam):
        return render(request, 'no_exam.html', {
            'active_page': 'exams',
            'message': 'This exam has no questions yet. Please check back later.',
        })

    is_valid, error_message = validate_exam_availability(exam, request.user)
    if not is_valid:
        return render(request, 'no_exam.html', {
            'active_page': 'exams',
            'message': error_message,
        })

    questions = get_exam_questions_for_student(exam)

    context = {
        'active_page': 'exams',
        'exam': exam,
        'questions': questions,
        'current_question': 1,
        'total_questions': questions.count(),
        'lab_current': 0,
        'lab_total': 2,
        'exam_duration_seconds': exam.duration_minutes * 60 if exam.duration_minutes else 0,
    }
    return render(request, 'exam_page.html', context)


@login_required(login_url='/auth/login/')
def courses_view(request):
    """Render the courses/subjects page."""
    context = {
        'active_page': 'subjects',
        'unread_notifications': 0,
    }
    try:
        from core.services.notification_service import get_unread_count
        context['unread_notifications'] = get_unread_count(request.user)
    except Exception:
        pass
    return render(request, 'courses.html', context)


@login_required(login_url='/auth/login/')
def homeworks_view(request):
    """Render the homeworks page."""
    context = {
        'active_page': 'homeworks',
        'unread_notifications': 0,
    }
    return render(request, 'homeworks.html', context)


@login_required(login_url='/auth/login/')
def statistics_view(request):
    """Render the statistics/results page."""
    context = {
        'active_page': 'results',
        'unread_notifications': 0,
    }
    try:
        from core.services.notification_service import get_unread_count
        context['unread_notifications'] = get_unread_count(request.user)
    except Exception:
        pass
    return render(request, 'statistics.html', context)


# ─────────────────────────────────────────────
# Phase 5B Views
# ─────────────────────────────────────────────

@login_required(login_url='/auth/login/')
def subjects_view(request):
    """Subjects management page (teacher/admin) or subject list (student)."""
    user = request.user
    context = {'active_page': 'subjects', 'unread_notifications': 0}
    try:
        from core.services.notification_service import get_unread_count
        context['unread_notifications'] = get_unread_count(user)
    except Exception:
        pass

    try:
        from subjects.models import Subject
        from schools.models import SchoolMembership
        membership = SchoolMembership.objects.filter(user=user, is_active=True).first()
        if membership:
            subjects = Subject.objects.filter(school=membership.school, is_active=True).select_related('department')
            context['subjects'] = subjects
            context['school'] = membership.school
            context['membership'] = membership
            context['is_teacher_or_admin'] = membership.role in ('teacher', 'school_admin')
    except Exception:
        context['subjects'] = []
        context['is_teacher_or_admin'] = False

    return render(request, 'subjects.html', context)


@login_required(login_url='/auth/login/')
def materials_view(request):
    """Study materials page."""
    user = request.user
    context = {'active_page': 'materials', 'unread_notifications': 0}
    try:
        from core.services.notification_service import get_unread_count
        context['unread_notifications'] = get_unread_count(user)
    except Exception:
        pass

    try:
        from materials.models import Material
        from schools.models import SchoolMembership
        membership = SchoolMembership.objects.filter(user=user, is_active=True).first()
        if membership:
            qs = Material.objects.filter(school=membership.school).select_related('subject', 'uploaded_by')
            if membership.role == 'student':
                qs = qs.filter(is_published=True)
            context['materials'] = qs.order_by('-created_at')[:50]
            context['school'] = membership.school
            context['membership'] = membership
            context['is_teacher_or_admin'] = membership.role in ('teacher', 'school_admin')
            # Subject filter options
            from subjects.models import Subject
            context['subjects'] = Subject.objects.filter(school=membership.school, is_active=True)
    except Exception:
        context['materials'] = []
        context['is_teacher_or_admin'] = False

    return render(request, 'materials.html', context)


@login_required(login_url='/auth/login/')
def exams_manage_view(request):
    """Exam management page (teacher/admin) or exam list (student)."""
    user = request.user
    context = {'active_page': 'exams', 'unread_notifications': 0}
    try:
        from core.services.notification_service import get_unread_count
        context['unread_notifications'] = get_unread_count(user)
    except Exception:
        pass

    try:
        from exams.models import Exam
        from schools.models import SchoolMembership
        membership = SchoolMembership.objects.filter(user=user, is_active=True).first()
        if membership:
            if membership.role in ('teacher', 'school_admin'):
                if membership.role == 'teacher':
                    exams = Exam.objects.filter(school=membership.school, created_by=user).select_related('subject')
                else:
                    exams = Exam.objects.filter(school=membership.school).select_related('subject', 'created_by')
            else:
                exams = Exam.objects.filter(school=membership.school, status='published').select_related('subject')
            context['exams'] = exams.order_by('-created_at')
            context['school'] = membership.school
            context['membership'] = membership
            context['is_teacher_or_admin'] = membership.role in ('teacher', 'school_admin')
            from subjects.models import Subject
            context['subjects'] = Subject.objects.filter(school=membership.school, is_active=True)
    except Exception:
        context['exams'] = []
        context['is_teacher_or_admin'] = False

    return render(request, 'exams_manage.html', context)


@login_required(login_url='/auth/login/')
def exam_create_view(request):
    """Create a new exam (teacher/admin only)."""
    user = request.user
    if user.role not in (User.Role.TEACHER, User.Role.SCHOOL_ADMIN, User.Role.PLATFORM_ADMIN):
        return redirect(get_role_redirect_url(user))

    context = {'active_page': 'exams', 'unread_notifications': 0, 'exam': None}
    try:
        from schools.models import SchoolMembership
        from subjects.models import Subject
        membership = SchoolMembership.objects.filter(user=user, is_active=True).first()
        if membership:
            context['subjects'] = Subject.objects.filter(school=membership.school, is_active=True)
            context['school'] = membership.school
    except Exception:
        context['subjects'] = []

    return render(request, 'exam_form.html', context)


@login_required(login_url='/auth/login/')
def exam_edit_view(request, exam_id):
    """Edit an existing exam (teacher/admin only)."""
    user = request.user
    if user.role not in (User.Role.TEACHER, User.Role.SCHOOL_ADMIN, User.Role.PLATFORM_ADMIN):
        return redirect(get_role_redirect_url(user))

    context = {'active_page': 'exams', 'unread_notifications': 0}
    try:
        from exams.models import Exam
        from subjects.models import Subject
        from schools.models import SchoolMembership
        membership = SchoolMembership.objects.filter(user=user, is_active=True).first()
        exam = Exam.objects.get(id=exam_id)
        context['exam'] = exam
        if membership:
            context['subjects'] = Subject.objects.filter(school=membership.school, is_active=True)
            context['school'] = membership.school
    except Exception:
        context['exam'] = None
        context['subjects'] = []

    return render(request, 'exam_form.html', context)


@login_required(login_url='/auth/login/')
def exam_questions_view(request, exam_id):
    """Question builder page for an exam (teacher/admin only)."""
    user = request.user
    if user.role not in (User.Role.TEACHER, User.Role.SCHOOL_ADMIN, User.Role.PLATFORM_ADMIN):
        return redirect(get_role_redirect_url(user))

    context = {'active_page': 'exams', 'unread_notifications': 0}
    try:
        from exams.models import Exam, Question
        exam = Exam.objects.select_related('subject').get(id=exam_id)
        questions = Question.objects.filter(exam=exam, is_active=True).order_by('order')
        context['exam'] = exam
        context['questions'] = questions
        context['question_count'] = questions.count()
    except Exception:
        context['exam'] = None
        context['questions'] = []
        context['question_count'] = 0

    return render(request, 'exam_questions.html', context)


@login_required(login_url='/auth/login/')
def results_view(request):
    """Results and analytics page."""
    user = request.user
    context = {'active_page': 'results', 'unread_notifications': 0}
    try:
        from core.services.notification_service import get_unread_count
        context['unread_notifications'] = get_unread_count(user)
    except Exception:
        pass

    try:
        from exams.models import ExamResult, ExamAttempt
        from schools.models import SchoolMembership
        membership = SchoolMembership.objects.filter(user=user, is_active=True).first()
        if membership:
            if membership.role == 'student':
                results = ExamResult.objects.filter(
                    student=user, exam__school=membership.school
                ).select_related('exam', 'exam__subject').order_by('-created_at')
                context['results'] = results
                # Compute stats
                if results.exists():
                    scores = [float(r.percentage) for r in results]
                    context['avg_score'] = round(sum(scores) / len(scores), 1)
                    context['best_score'] = max(scores)
                    context['total_exams'] = len(scores)
                    context['passed_count'] = sum(1 for r in results if r.passed)
                    # Chart data
                    context['chart_labels'] = [r.exam.title[:20] for r in results[:10]]
                    context['chart_scores'] = [float(r.percentage) for r in results[:10]]
                    # Subject performance
                    subject_scores = {}
                    for r in results:
                        sname = r.exam.subject.name
                        if sname not in subject_scores:
                            subject_scores[sname] = []
                        subject_scores[sname].append(float(r.percentage))
                    context['subject_labels'] = list(subject_scores.keys())
                    context['subject_avgs'] = [round(sum(v)/len(v), 1) for v in subject_scores.values()]
                else:
                    context['avg_score'] = 0
                    context['best_score'] = 0
                    context['total_exams'] = 0
                    context['passed_count'] = 0
                    context['chart_labels'] = []
                    context['chart_scores'] = []
                    context['subject_labels'] = []
                    context['subject_avgs'] = []
            else:
                # Teacher/admin sees all results for their school
                results = ExamResult.objects.filter(
                    exam__school=membership.school
                ).select_related('exam', 'exam__subject', 'student').order_by('-created_at')[:50]
                context['results'] = results
                context['is_teacher_or_admin'] = True
    except Exception:
        context['results'] = []

    return render(request, 'results.html', context)


@login_required(login_url='/auth/login/')
def notifications_view(request):
    """Notification center page."""
    user = request.user
    context = {'active_page': 'notifications', 'unread_notifications': 0}

    try:
        from notifications.models import Notification
        notifications = Notification.objects.filter(
            recipient=user
        ).order_by('-created_at')[:50]
        context['notifications'] = notifications
        context['unread_count'] = notifications.filter(is_read=False).count()
        context['unread_notifications'] = context['unread_count']
    except Exception:
        context['notifications'] = []
        context['unread_count'] = 0

    return render(request, 'notifications.html', context)


def offline_view(request):
    """PWA offline fallback page — served when user has no internet connection."""
    return render(request, 'offline.html', status=200)
