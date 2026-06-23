"""
Views for the achievements app.
Phase 6D: Leaderboards, Badges & Achievements, Student Achievement Page, Reports.

Endpoints:
  Leaderboards:
    GET  /api/v1/achievements/leaderboard/school/
    GET  /api/v1/achievements/leaderboard/class/<classroom_id>/
    GET  /api/v1/achievements/leaderboard/subject/<subject_id>/
    GET  /api/v1/achievements/leaderboard/my-rank/

  Badges:
    GET  /api/v1/achievements/badges/                  — all available badges
    GET  /api/v1/achievements/badges/my/               — student's earned badges
    POST /api/v1/achievements/badges/mark-seen/        — mark badges as seen

  Achievement Page:
    GET  /api/v1/achievements/my/                      — full achievement page

  Reports:
    GET  /api/v1/achievements/reports/student/         — student performance report
    GET  /api/v1/achievements/reports/subject/         — subject report
    GET  /api/v1/achievements/reports/class/           — class report (teacher/admin)
    GET  /api/v1/achievements/reports/school/          — school analytics (admin)
"""

from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import (
    HasSchoolContext,
    IsSchoolAdmin,
    IsSchoolAdminOrTeacher,
    IsStudent,
)
from achievements.models import Badge, StudentBadge, LeaderboardEntry
from achievements.serializers import (
    BadgeSerializer,
    StudentBadgeSerializer,
    StudentBadgeMarkSeenSerializer,
    LeaderboardEntrySerializer,
    AchievementPageSerializer,
    ReportQuerySerializer,
    LeaderboardQuerySerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_term(school, term_id):
    """Return Term instance or None."""
    if not term_id:
        return None
    from schools.models import Term
    return Term.objects.filter(id=term_id, academic_year__school=school).first()


def _resolve_classroom(school, classroom_id):
    from schools.models import ClassRoom
    return ClassRoom.objects.filter(id=classroom_id, school=school).first()


def _resolve_subject(school, subject_id):
    from subjects.models import Subject
    return Subject.objects.filter(id=subject_id, school=school).first()


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class SchoolLeaderboardView(APIView):
    """
    GET /api/v1/achievements/leaderboard/school/
    Returns the school-wide leaderboard.
    Optional query params: term_id, limit, rebuild (admin/teacher only).
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request):
        school = request.school
        query_ser = LeaderboardQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        params = query_ser.validated_data

        term = _resolve_term(school, params.get('term_id'))
        limit = params.get('limit', 20)
        rebuild = params.get('rebuild', False)

        # Only admins/teachers can force a rebuild
        if rebuild and hasattr(request, 'school_membership') and \
                request.school_membership.role in ('school_admin', 'teacher'):
            from achievements.services.leaderboard_service import rebuild_school_leaderboard
            rebuild_school_leaderboard(school, term=term, limit=50)

        from achievements.services.leaderboard_service import get_school_leaderboard
        entries = get_school_leaderboard(school, term=term, limit=limit)
        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response({
            'leaderboard_type': 'school',
            'term': term.name if term else None,
            'count': len(entries),
            'results': serializer.data,
        })


class ClassLeaderboardView(APIView):
    """
    GET /api/v1/achievements/leaderboard/class/<classroom_id>/
    Returns the leaderboard for a specific classroom.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request, classroom_id):
        school = request.school
        classroom = _resolve_classroom(school, classroom_id)
        if not classroom:
            return Response({'detail': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)

        query_ser = LeaderboardQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        params = query_ser.validated_data

        term = _resolve_term(school, params.get('term_id'))
        limit = params.get('limit', 50)
        rebuild = params.get('rebuild', False)

        if rebuild and hasattr(request, 'school_membership') and \
                request.school_membership.role in ('school_admin', 'teacher'):
            from achievements.services.leaderboard_service import rebuild_class_leaderboard
            rebuild_class_leaderboard(school, classroom, term=term, limit=50)

        from achievements.services.leaderboard_service import get_class_leaderboard
        entries = get_class_leaderboard(school, classroom, term=term, limit=limit)
        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response({
            'leaderboard_type': 'class',
            'classroom': classroom.name,
            'term': term.name if term else None,
            'count': len(entries),
            'results': serializer.data,
        })


class SubjectLeaderboardView(APIView):
    """
    GET /api/v1/achievements/leaderboard/subject/<subject_id>/
    Returns the leaderboard for a specific subject.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request, subject_id):
        school = request.school
        subject = _resolve_subject(school, subject_id)
        if not subject:
            return Response({'detail': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)

        query_ser = LeaderboardQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        params = query_ser.validated_data

        term = _resolve_term(school, params.get('term_id'))
        limit = params.get('limit', 50)
        rebuild = params.get('rebuild', False)

        if rebuild and hasattr(request, 'school_membership') and \
                request.school_membership.role in ('school_admin', 'teacher'):
            from achievements.services.leaderboard_service import rebuild_subject_leaderboard
            rebuild_subject_leaderboard(school, subject, term=term, limit=50)

        from achievements.services.leaderboard_service import get_subject_leaderboard
        entries = get_subject_leaderboard(school, subject, term=term, limit=limit)
        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response({
            'leaderboard_type': 'subject',
            'subject': subject.name,
            'subject_code': subject.code,
            'term': term.name if term else None,
            'count': len(entries),
            'results': serializer.data,
        })


class MyRankView(APIView):
    """
    GET /api/v1/achievements/leaderboard/my-rank/
    Returns the current student's rank across school, class, and subject leaderboards.
    Query params: term_id, classroom_id, subject_id
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request):
        school = request.school
        student = request.user

        term_id = request.query_params.get('term_id')
        classroom_id = request.query_params.get('classroom_id')
        subject_id = request.query_params.get('subject_id')

        term = _resolve_term(school, term_id)
        classroom = _resolve_classroom(school, classroom_id) if classroom_id else None
        subject = _resolve_subject(school, subject_id) if subject_id else None

        from achievements.services.leaderboard_service import get_student_rank
        school_rank = get_student_rank(school, student, term=term, leaderboard_type='school')
        class_rank = get_student_rank(
            school, student, term=term, leaderboard_type='class', classroom=classroom
        ) if classroom else None
        subject_rank = get_student_rank(
            school, student, term=term, leaderboard_type='subject', subject=subject
        ) if subject else None

        return Response({
            'school_rank': school_rank,
            'class_rank': class_rank,
            'subject_rank': subject_rank,
        })


# ─────────────────────────────────────────────────────────────────────────────
# BADGE VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class BadgeListView(generics.ListAPIView):
    """
    GET /api/v1/achievements/badges/
    List all active badges available in this school (global + school-specific).
    """
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        school = self.request.school
        from django.db.models import Q
        return Badge.objects.filter(
            is_active=True
        ).filter(
            Q(is_global=True) | Q(school=school)
        ).order_by('tier', 'name')


class MyBadgesView(generics.ListAPIView):
    """
    GET /api/v1/achievements/badges/my/
    List all badges earned by the current student.
    """
    serializer_class = StudentBadgeSerializer
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return StudentBadge.objects.filter(
            student=self.request.user,
            school=self.request.school,
        ).select_related('badge').order_by('-awarded_at')


class MarkBadgesSeenView(APIView):
    """
    POST /api/v1/achievements/badges/mark-seen/
    Mark one or more badges as seen. Omit badge_ids to mark all unseen.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def post(self, request):
        serializer = StudentBadgeMarkSeenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        badge_ids = serializer.validated_data.get('badge_ids')

        qs = StudentBadge.objects.filter(
            student=request.user,
            school=request.school,
            is_seen=False,
        )
        if badge_ids:
            qs = qs.filter(id__in=badge_ids)

        updated = qs.update(is_seen=True)
        return Response({'marked_seen': updated})


# ─────────────────────────────────────────────────────────────────────────────
# ACHIEVEMENT PAGE VIEW
# ─────────────────────────────────────────────────────────────────────────────

class MyAchievementPageView(APIView):
    """
    GET /api/v1/achievements/my/
    Full achievement page for the current student:
      - All earned badges (with tier breakdown)
      - School rank and class rank
      - Performance summary (avg score, total exams, practice sessions)
    Query params: term_id
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request):
        school = request.school
        student = request.user
        term_id = request.query_params.get('term_id')
        term = _resolve_term(school, term_id)

        # Badges
        badges_qs = StudentBadge.objects.filter(
            student=student, school=school
        ).select_related('badge').order_by('-awarded_at')
        badges_list = list(badges_qs)

        unseen_count = sum(1 for b in badges_list if not b.is_seen)
        bronze = sum(1 for b in badges_list if b.badge.tier == 'bronze')
        silver = sum(1 for b in badges_list if b.badge.tier == 'silver')
        gold = sum(1 for b in badges_list if b.badge.tier == 'gold')
        platinum = sum(1 for b in badges_list if b.badge.tier == 'platinum')

        # School rank
        from achievements.services.leaderboard_service import get_student_rank
        school_stats = get_student_rank(school, student, term=term, leaderboard_type='school')

        # Class rank — find student's current classroom
        class_rank_val = None
        try:
            from schools.models import StudentClassAssignment
            assignment = StudentClassAssignment.objects.filter(
                student=student,
                classroom__school=school,
                status='active',
            ).select_related('classroom').first()
            if assignment:
                class_stats = get_student_rank(
                    school, student, term=term,
                    leaderboard_type='class',
                    classroom=assignment.classroom,
                )
                class_rank_val = class_stats.get('rank')
        except Exception:
            pass

        # Total students in school (for context)
        total_in_school = LeaderboardEntry.objects.filter(
            school=school,
            leaderboard_type=LeaderboardEntry.LeaderboardType.SCHOOL,
        )
        if term:
            total_in_school = total_in_school.filter(term=term)
        total_in_school = total_in_school.count()

        data = {
            'total_badges': len(badges_list),
            'unseen_badges': unseen_count,
            'badges': StudentBadgeSerializer(badges_list, many=True).data,
            'school_rank': school_stats.get('rank'),
            'class_rank': class_rank_val,
            'total_students_in_school': total_in_school,
            'average_score': school_stats.get('average_score', 0),
            'highest_score': school_stats.get('highest_score', 0),
            'total_exams': school_stats.get('total_exams', 0),
            'total_practice': school_stats.get('total_practice', 0),
            'activity_score': school_stats.get('activity_score', 0),
            'bronze_count': bronze,
            'silver_count': silver,
            'gold_count': gold,
            'platinum_count': platinum,
        }
        serializer = AchievementPageSerializer(data)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# REPORT VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class StudentPerformanceReportView(APIView):
    """
    GET /api/v1/achievements/reports/student/
    Generate a student performance report (HTML, printable as PDF).
    Students see their own report; admins/teachers can pass ?student_id=<uuid>.
    Query params: term_id, student_id (admin/teacher only)
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request):
        school = request.school
        query_ser = ReportQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        params = query_ser.validated_data

        term = _resolve_term(school, params.get('term_id'))

        # Determine target student
        student_id = params.get('student_id')
        if student_id:
            # Only admins/teachers can view other students' reports
            if not (hasattr(request, 'school_membership') and
                    request.school_membership.role in ('school_admin', 'teacher')):
                return Response(
                    {'detail': 'Only admins and teachers can view other students\' reports.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            from accounts.models import User
            student = User.objects.filter(id=student_id).first()
            if not student:
                return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            student = request.user

        from core.services.report_service import generate_student_performance_report
        report = generate_student_performance_report(student, school, term=term)
        return HttpResponse(
            report['content'],
            content_type=report['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{report["filename"]}"',
            },
        )


class SubjectReportView(APIView):
    """
    GET /api/v1/achievements/reports/subject/
    Generate a subject-specific performance report for a student.
    Query params: subject_id (required), term_id, student_id (admin/teacher only)
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request):
        school = request.school
        query_ser = ReportQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        params = query_ser.validated_data

        subject_id = params.get('subject_id')
        if not subject_id:
            return Response(
                {'detail': 'subject_id is required for subject reports.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = _resolve_subject(school, subject_id)
        if not subject:
            return Response({'detail': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)

        term = _resolve_term(school, params.get('term_id'))

        student_id = params.get('student_id')
        if student_id:
            if not (hasattr(request, 'school_membership') and
                    request.school_membership.role in ('school_admin', 'teacher')):
                return Response(
                    {'detail': 'Only admins and teachers can view other students\' reports.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            from accounts.models import User
            student = User.objects.filter(id=student_id).first()
            if not student:
                return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            student = request.user

        from core.services.report_service import generate_subject_report
        report = generate_subject_report(student, school, subject, term=term)
        return HttpResponse(
            report['content'],
            content_type=report['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{report["filename"]}"',
            },
        )


class ClassPerformanceReportView(APIView):
    """
    GET /api/v1/achievements/reports/class/
    Generate a class performance report (teacher/admin only).
    Query params: classroom_id (required), term_id
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get(self, request):
        school = request.school
        query_ser = ReportQuerySerializer(data=request.query_params)
        query_ser.is_valid(raise_exception=True)
        params = query_ser.validated_data

        classroom_id = params.get('classroom_id')
        if not classroom_id:
            return Response(
                {'detail': 'classroom_id is required for class reports.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        classroom = _resolve_classroom(school, classroom_id)
        if not classroom:
            return Response({'detail': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)

        term = _resolve_term(school, params.get('term_id'))

        from core.services.report_service import generate_class_performance_report
        report = generate_class_performance_report(school, classroom, term=term)
        return HttpResponse(
            report['content'],
            content_type=report['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{report["filename"]}"',
            },
        )


class SchoolAnalyticsReportView(APIView):
    """
    GET /api/v1/achievements/reports/school/
    Generate a school analytics report (admin only).
    Query params: term_id
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        school = request.school
        term_id = request.query_params.get('term_id')
        term = _resolve_term(school, term_id)

        from core.services.report_service import generate_school_analytics_report
        report = generate_school_analytics_report(school, term=term)
        return HttpResponse(
            report['content'],
            content_type=report['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{report["filename"]}"',
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: Rebuild leaderboards manually
# ─────────────────────────────────────────────────────────────────────────────

class RebuildLeaderboardsView(APIView):
    """
    POST /api/v1/achievements/leaderboard/rebuild/
    Manually trigger a full leaderboard rebuild for the school (admin only).
    Body: { "term_id": "<uuid>" }  (optional)
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        school = request.school
        term_id = request.data.get('term_id')
        term = _resolve_term(school, term_id)

        from achievements.services.leaderboard_service import rebuild_school_leaderboard
        entries = rebuild_school_leaderboard(school, term=term, limit=100)
        return Response({
            'detail': 'School leaderboard rebuilt successfully.',
            'entries_updated': len(entries),
            'term': term.name if term else None,
        })
