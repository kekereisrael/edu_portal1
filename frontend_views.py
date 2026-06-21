"""
Views for serving the frontend templates.
"""

from django.shortcuts import render


def dashboard_view(request):
    """Render the main dashboard page."""
    context = {
        'active_page': 'dashboard',
    }
    return render(request, 'dashboard.html', context)


def exam_page_view(request):
    """Render the exam taking page."""
    context = {
        'active_page': 'exams',
        'current_question': 1,
        'total_questions': 14,
        'lab_current': 0,
        'lab_total': 2,
        'exam_duration_seconds': 28767,
    }
    return render(request, 'exam_page.html', context)


def courses_view(request):
    """Render the courses page."""
    context = {
        'active_page': 'courses',
    }
    return render(request, 'courses.html', context)


def homeworks_view(request):
    """Render the homeworks page."""
    context = {
        'active_page': 'homeworks',
    }
    return render(request, 'homeworks.html', context)


def statistics_view(request):
    """Render the statistics page."""
    context = {
        'active_page': 'statistics',
    }
    return render(request, 'statistics.html', context)
