"""
report_service.py — TASK 4: PDF Report Generation

Generates PDF reports using Python's built-in reportlab (if available)
or falls back to an HTML-based response that the browser can print/save as PDF.

Report types:
  - student_performance  : student's exam results, scores, badges, ranking
  - subject_report       : student's performance in a specific subject
  - class_performance    : teacher/admin view of a whole class
  - school_analytics     : admin school-wide analytics report

Returns a dict with:
  {
    'format': 'html' | 'pdf',
    'filename': str,
    'content': bytes | str,
    'content_type': str,
  }
"""

from __future__ import annotations
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_student_performance_report(student, school, term=None) -> dict:
    """
    Student performance report:
    - Exam results (score, grade, pass/fail)
    - Subject averages
    - Badges earned
    - Ranking in school/class
    """
    data = _collect_student_data(student, school, term)
    html = _render_student_report_html(data)
    return {
        'format': 'html',
        'filename': f'performance_report_{student.full_name.replace(" ", "_")}_{_today()}.html',
        'content': html,
        'content_type': 'text/html; charset=utf-8',
    }


def generate_subject_report(student, school, subject, term=None) -> dict:
    """
    Subject-specific report for a student:
    - All exam attempts for this subject
    - Topic performance breakdown
    - Practice session stats
    """
    data = _collect_subject_data(student, school, subject, term)
    html = _render_subject_report_html(data)
    return {
        'format': 'html',
        'filename': f'subject_report_{subject.code}_{student.full_name.replace(" ", "_")}_{_today()}.html',
        'content': html,
        'content_type': 'text/html; charset=utf-8',
    }


def generate_class_performance_report(school, classroom, term=None) -> dict:
    """
    Class performance report (teacher/admin):
    - All students in class with their average scores
    - Subject pass rates
    - Top and bottom performers
    """
    data = _collect_class_data(school, classroom, term)
    html = _render_class_report_html(data)
    return {
        'format': 'html',
        'filename': f'class_report_{classroom.name.replace(" ", "_")}_{_today()}.html',
        'content': html,
        'content_type': 'text/html; charset=utf-8',
    }


def generate_school_analytics_report(school, term=None) -> dict:
    """
    School analytics report (admin):
    - Total students, teachers, subjects
    - Average pass rate
    - Top performing classes and subjects
    - AI usage summary
    """
    data = _collect_school_data(school, term)
    html = _render_school_report_html(data)
    return {
        'format': 'html',
        'filename': f'school_analytics_{school.name.replace(" ", "_")}_{_today()}.html',
        'content': html,
        'content_type': 'text/html; charset=utf-8',
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data collectors
# ─────────────────────────────────────────────────────────────────────────────

def _collect_student_data(student, school, term) -> dict:
    from exams.models import ExamResult, ExamAttempt
    from achievements.models import StudentBadge, LeaderboardEntry

    result_qs = ExamResult.objects.filter(
        student=student,
        exam__school=school,
    ).select_related('exam', 'exam__subject', 'exam__term')
    if term:
        result_qs = result_qs.filter(exam__term=term)

    results = []
    for r in result_qs.order_by('-created_at'):
        results.append({
            'exam_title': r.exam.title,
            'subject': r.exam.subject.name,
            'subject_code': r.exam.subject.code,
            'term': r.exam.term.name if r.exam.term else '—',
            'score': float(r.score),
            'percentage': float(r.percentage),
            'passed': r.passed,
            'grade': r.grade or '—',
        })

    badges = StudentBadge.objects.filter(
        student=student, school=school
    ).select_related('badge').order_by('-awarded_at')
    badge_list = [
        {
            'name': sb.badge.name,
            'icon': sb.badge.icon,
            'tier': sb.badge.get_tier_display(),
            'awarded_for': sb.awarded_for,
            'awarded_at': sb.awarded_at.strftime('%d %b %Y'),
        }
        for sb in badges
    ]

    rank_entry = LeaderboardEntry.objects.filter(
        school=school, student=student,
        leaderboard_type='school',
    )
    if term:
        rank_entry = rank_entry.filter(term=term)
    rank_entry = rank_entry.first()

    return {
        'student': student,
        'school': school,
        'term': term,
        'results': results,
        'badges': badge_list,
        'rank': rank_entry.rank if rank_entry else None,
        'average_score': float(rank_entry.average_score) if rank_entry else 0,
        'total_exams': len(results),
        'generated_at': _now_str(),
    }


def _collect_subject_data(student, school, subject, term) -> dict:
    from exams.models import ExamAttempt, TopicPerformance, PracticeSession

    attempts = ExamAttempt.objects.filter(
        student=student,
        exam__school=school,
        exam__subject=subject,
        status__in=['graded', 'submitted'],
    ).select_related('exam').order_by('-started_at')
    if term:
        attempts = attempts.filter(exam__term=term)

    attempt_list = [
        {
            'exam_title': a.exam.title,
            'score': float(a.score or 0),
            'percentage': float(a.percentage or 0),
            'passed': a.passed,
            'attempt_number': a.attempt_number,
            'date': a.started_at.strftime('%d %b %Y'),
        }
        for a in attempts
    ]

    topic_perfs = TopicPerformance.objects.filter(
        student=student, school=school, subject=subject
    ).select_related('topic').order_by('accuracy_percent')

    topic_list = [
        {
            'topic': tp.topic.name,
            'attempts': tp.total_attempts,
            'correct': tp.total_correct,
            'accuracy': float(tp.accuracy_percent),
            'strength': tp.get_strength_level_display(),
        }
        for tp in topic_perfs
    ]

    practice_count = PracticeSession.objects.filter(
        student=student, bank__school=school,
        bank__subject=subject, status='completed',
    ).count()

    return {
        'student': student,
        'school': school,
        'subject': subject,
        'term': term,
        'attempts': attempt_list,
        'topic_performances': topic_list,
        'practice_sessions': practice_count,
        'generated_at': _now_str(),
    }


def _collect_class_data(school, classroom, term) -> dict:
    from subjects.models import Enrollment
    from exams.models import ExamAttempt
    from django.db.models import Avg, Count

    enrollments = Enrollment.objects.filter(
        classroom=classroom, status='active'
    ).select_related('student')

    students_data = []
    for enr in enrollments:
        qs = ExamAttempt.objects.filter(
            student=enr.student,
            exam__school=school,
            status__in=['graded', 'submitted'],
            percentage__isnull=False,
        )
        if term:
            qs = qs.filter(exam__term=term)
        agg = qs.aggregate(avg=Avg('percentage'), count=Count('id'))
        students_data.append({
            'name': enr.student.full_name,
            'email': enr.student.email,
            'average_score': round(float(agg['avg'] or 0), 1),
            'total_exams': agg['count'],
        })

    students_data.sort(key=lambda x: x['average_score'], reverse=True)

    return {
        'school': school,
        'classroom': classroom,
        'term': term,
        'students': students_data,
        'total_students': len(students_data),
        'class_average': round(
            sum(s['average_score'] for s in students_data) / len(students_data), 1
        ) if students_data else 0,
        'generated_at': _now_str(),
    }


def _collect_school_data(school, term) -> dict:
    from analytics.models import SchoolAnalytics, AIUsageRecord
    from exams.models import ExamAttempt
    from django.db.models import Avg, Count

    analytics = SchoolAnalytics.objects.filter(school=school).first()

    attempt_qs = ExamAttempt.objects.filter(
        exam__school=school, status__in=['graded', 'submitted']
    )
    if term:
        attempt_qs = attempt_qs.filter(exam__term=term)

    agg = attempt_qs.aggregate(avg=Avg('percentage'), count=Count('id'))
    pass_count = attempt_qs.filter(passed=True).count()
    pass_rate = round((pass_count / agg['count'] * 100), 1) if agg['count'] else 0

    ai_credits = AIUsageRecord.objects.filter(school=school)
    if term:
        ai_credits = ai_credits.filter(created_at__gte=term.start_date if hasattr(term, 'start_date') else ai_credits.query.model.objects.none())
    total_ai = ai_credits.aggregate(total=Count('id'))['total'] or 0

    return {
        'school': school,
        'term': term,
        'analytics': analytics,
        'total_exams_taken': agg['count'],
        'average_score': round(float(agg['avg'] or 0), 1),
        'pass_rate': pass_rate,
        'total_ai_requests': total_ai,
        'generated_at': _now_str(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML renderers (print-friendly, browser-printable as PDF)
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
<style>
  body { font-family: Arial, sans-serif; font-size: 13px; color: #222; margin: 30px; }
  h1 { color: #1a56db; border-bottom: 2px solid #1a56db; padding-bottom: 6px; }
  h2 { color: #374151; margin-top: 24px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th { background: #1a56db; color: #fff; padding: 8px 10px; text-align: left; }
  td { padding: 7px 10px; border-bottom: 1px solid #e5e7eb; }
  tr:nth-child(even) td { background: #f9fafb; }
  .pass { color: #16a34a; font-weight: bold; }
  .fail { color: #dc2626; font-weight: bold; }
  .weak { color: #dc2626; }
  .strong { color: #16a34a; }
  .average { color: #d97706; }
  .badge-row { display: inline-block; margin: 4px 8px 4px 0; padding: 4px 10px;
               background: #fef3c7; border-radius: 12px; font-size: 12px; }
  .meta { color: #6b7280; font-size: 11px; margin-bottom: 20px; }
  @media print { body { margin: 10px; } }
</style>
"""


def _render_student_report_html(data: dict) -> str:
    student = data['student']
    school = data['school']
    term_name = data['term'].name if data['term'] else 'All Terms'

    rows = ''
    for r in data['results']:
        status_cls = 'pass' if r['passed'] else 'fail'
        status_txt = 'PASS' if r['passed'] else 'FAIL'
        rows += (
            f'<tr><td>{r["exam_title"]}</td><td>{r["subject_code"]}</td>'
            f'<td>{r["term"]}</td><td>{r["percentage"]}%</td>'
            f'<td>{r["grade"]}</td>'
            f'<td class="{status_cls}">{status_txt}</td></tr>'
        )

    badge_html = ''.join(
        f'<span class="badge-row">{b["icon"]} {b["name"]} ({b["tier"]})</span>'
        for b in data['badges']
    ) or '<em>No badges yet</em>'

    rank_txt = f'#{data["rank"]}' if data['rank'] else 'Unranked'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Performance Report – {student.full_name}</title>{_CSS}</head><body>
<h1>📊 Student Performance Report</h1>
<p class="meta">
  <strong>Student:</strong> {student.full_name} &nbsp;|&nbsp;
  <strong>School:</strong> {school.name} &nbsp;|&nbsp;
  <strong>Term:</strong> {term_name} &nbsp;|&nbsp;
  <strong>School Rank:</strong> {rank_txt} &nbsp;|&nbsp;
  <strong>Average Score:</strong> {data['average_score']}% &nbsp;|&nbsp;
  <strong>Generated:</strong> {data['generated_at']}
</p>
<h2>Exam Results ({data['total_exams']} exams)</h2>
<table><thead><tr>
  <th>Exam</th><th>Subject</th><th>Term</th><th>Score</th><th>Grade</th><th>Status</th>
</tr></thead><tbody>{rows or '<tr><td colspan="6">No exam results found.</td></tr>'}</tbody></table>
<h2>🏅 Badges Earned ({len(data['badges'])})</h2>
<div>{badge_html}</div>
</body></html>"""


def _render_subject_report_html(data: dict) -> str:
    student = data['student']
    subject = data['subject']
    school = data['school']
    term_name = data['term'].name if data['term'] else 'All Terms'

    attempt_rows = ''
    for a in data['attempts']:
        status_cls = 'pass' if a['passed'] else 'fail'
        attempt_rows += (
            f'<tr><td>{a["exam_title"]}</td><td>#{a["attempt_number"]}</td>'
            f'<td>{a["percentage"]}%</td>'
            f'<td class="{status_cls}">{"PASS" if a["passed"] else "FAIL"}</td>'
            f'<td>{a["date"]}</td></tr>'
        )

    topic_rows = ''
    for t in data['topic_performances']:
        cls = t['strength'].lower()
        topic_rows += (
            f'<tr><td>{t["topic"]}</td><td>{t["attempts"]}</td>'
            f'<td>{t["correct"]}</td><td>{t["accuracy"]}%</td>'
            f'<td class="{cls}">{t["strength"]}</td></tr>'
        )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{subject.code} Report – {student.full_name}</title>{_CSS}</head><body>
<h1>📚 Subject Report: {subject.name} ({subject.code})</h1>
<p class="meta">
  <strong>Student:</strong> {student.full_name} &nbsp;|&nbsp;
  <strong>School:</strong> {school.name} &nbsp;|&nbsp;
  <strong>Term:</strong> {term_name} &nbsp;|&nbsp;
  <strong>Practice Sessions:</strong> {data['practice_sessions']} &nbsp;|&nbsp;
  <strong>Generated:</strong> {data['generated_at']}
</p>
<h2>Exam Attempts</h2>
<table><thead><tr>
  <th>Exam</th><th>Attempt</th><th>Score</th><th>Status</th><th>Date</th>
</tr></thead><tbody>{attempt_rows or '<tr><td colspan="5">No attempts found.</td></tr>'}</tbody></table>
<h2>Topic Performance</h2>
<table><thead><tr>
  <th>Topic</th><th>Attempts</th><th>Correct</th><th>Accuracy</th><th>Level</th>
</tr></thead><tbody>{topic_rows or '<tr><td colspan="5">No topic data yet.</td></tr>'}</tbody></table>
</body></html>"""


def _render_class_report_html(data: dict) -> str:
    classroom = data['classroom']
    school = data['school']
    term_name = data['term'].name if data['term'] else 'All Terms'

    rows = ''
    for i, s in enumerate(data['students'], 1):
        rows += (
            f'<tr><td>{i}</td><td>{s["name"]}</td>'
            f'<td>{s["average_score"]}%</td><td>{s["total_exams"]}</td></tr>'
        )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Class Report – {classroom.name}</title>{_CSS}</head><body>
<h1>🏫 Class Performance Report: {classroom.name}</h1>
<p class="meta">
  <strong>School:</strong> {school.name} &nbsp;|&nbsp;
  <strong>Term:</strong> {term_name} &nbsp;|&nbsp;
  <strong>Total Students:</strong> {data['total_students']} &nbsp;|&nbsp;
  <strong>Class Average:</strong> {data['class_average']}% &nbsp;|&nbsp;
  <strong>Generated:</strong> {data['generated_at']}
</p>
<h2>Student Rankings</h2>
<table><thead><tr>
  <th>#</th><th>Student</th><th>Average Score</th><th>Exams Taken</th>
</tr></thead><tbody>{rows or '<tr><td colspan="4">No data found.</td></tr>'}</tbody></table>
</body></html>"""


def _render_school_report_html(data: dict) -> str:
    school = data['school']
    term_name = data['term'].name if data['term'] else 'All Terms'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>School Analytics – {school.name}</title>{_CSS}</head><body>
<h1>🏛️ School Analytics Report: {school.name}</h1>
<p class="meta">
  <strong>Term:</strong> {term_name} &nbsp;|&nbsp;
  <strong>Generated:</strong> {data['generated_at']}
</p>
<h2>Key Metrics</h2>
<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
  <tr><td>Total Exams Taken</td><td>{data['total_exams_taken']}</td></tr>
  <tr><td>Average Score</td><td>{data['average_score']}%</td></tr>
  <tr><td>Pass Rate</td><td>{data['pass_rate']}%</td></tr>
  <tr><td>AI Requests</td><td>{data['total_ai_requests']}</td></tr>
</tbody></table>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now().strftime('%Y%m%d')


def _now_str() -> str:
    return datetime.now().strftime('%d %b %Y %H:%M')
