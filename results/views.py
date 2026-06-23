"""
Views for the results app — Score Entry, Report Cards, Analytics, Publishing.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Avg, Max, Min, Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasSchoolContext, IsSchoolAdmin, IsTeacher, IsSchoolAdminOrTeacher

from .models import GradeConfig, ResultSheet, StudentScore, ReportCard, ScoreEntryBatch
from .serializers import (
    GradeConfigSerializer,
    GradeConfigNigerianResetSerializer,
    ResultSheetSerializer,
    ResultSheetCreateSerializer,
    PublishResultSheetSerializer,
    StudentScoreSerializer,
    StudentScoreCreateSerializer,
    BulkScoreEntrySerializer,
    ReportCardSerializer,
    ReportCardUpdateSerializer,
    SubjectScoreLineSerializer,
    ScoreEntryBatchSerializer,
    ClassAnalyticsSerializer,
    StudentTrendSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_grade_config(school):
    """Return the school's GradeConfig, creating it with Nigerian defaults if absent."""
    config, _ = GradeConfig.objects.get_or_create(school=school)
    return config


def _recompute_positions(result_sheet):
    """
    Recompute class_position for all ReportCards in a ResultSheet,
    ranked by average_score descending.
    """
    cards = list(
        ReportCard.objects.filter(result_sheet=result_sheet)
        .order_by('-average_score', 'student__last_name')
    )
    total = len(cards)
    for rank, card in enumerate(cards, start=1):
        card.class_position = rank
        card.out_of = total
    ReportCard.objects.bulk_update(cards, ['class_position', 'out_of'])


def _get_or_create_report_card(result_sheet, student):
    card, _ = ReportCard.objects.get_or_create(
        result_sheet=result_sheet,
        student=student,
    )
    return card


# ─────────────────────────────────────────────────────────────────────────────
# GRADE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

class GradeConfigView(APIView):
    """
    GET  /results/grade-config/       — retrieve school's grade config
    PUT  /results/grade-config/       — full update
    PATCH /results/grade-config/      — partial update
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def _get_config(self, request):
        return _get_or_create_grade_config(request.school)

    def get(self, request):
        config = self._get_config(request)
        return Response(GradeConfigSerializer(config).data)

    def put(self, request):
        if not (request.school_membership and
                request.school_membership.role == 'school_admin'):
            return Response(
                {'detail': 'Only school admins can update grade config.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        config = self._get_config(request)
        serializer = GradeConfigSerializer(config, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        if not (request.school_membership and
                request.school_membership.role == 'school_admin'):
            return Response(
                {'detail': 'Only school admins can update grade config.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        config = self._get_config(request)
        serializer = GradeConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class GradeConfigNigerianResetView(APIView):
    """
    POST /results/grade-config/reset-nigerian/
    Resets grade bands to standard Nigerian A1–F9 scale.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = GradeConfigNigerianResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = _get_or_create_grade_config(request.school)
        config.bands = GradeConfig.nigerian_default_bands()
        config.system = GradeConfig.GradeSystem.NIGERIAN
        config.save(update_fields=['bands', 'system', 'updated_at'])
        return Response({
            'detail': 'Grade config reset to Nigerian A1–F9 defaults.',
            'config': GradeConfigSerializer(config).data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# RESULT SHEETS
# ─────────────────────────────────────────────────────────────────────────────

class ResultSheetListCreateView(generics.ListCreateAPIView):
    """
    GET  /results/sheets/             — list result sheets for school
    POST /results/sheets/             — create a new result sheet
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ResultSheetCreateSerializer
        return ResultSheetSerializer

    def get_queryset(self):
        school = self.request.school
        qs = ResultSheet.objects.filter(school=school).select_related(
            'classroom', 'term', 'term__academic_year',
            'academic_session', 'published_by',
        )
        # Filters
        term_id = self.request.query_params.get('term')
        classroom_id = self.request.query_params.get('classroom')
        status_filter = self.request.query_params.get('status')
        if term_id:
            qs = qs.filter(term_id=term_id)
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class ResultSheetDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /results/sheets/<id>/
    PATCH  /results/sheets/<id>/
    DELETE /results/sheets/<id>/
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    serializer_class = ResultSheetSerializer

    def get_queryset(self):
        return ResultSheet.objects.filter(school=self.request.school).select_related(
            'classroom', 'term', 'term__academic_year', 'published_by',
        )

    def destroy(self, request, *args, **kwargs):
        sheet = self.get_object()
        if sheet.is_published:
            return Response(
                {'detail': 'Cannot delete a published result sheet. Unpublish first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class PublishResultSheetView(APIView):
    """
    POST /results/sheets/<id>/publish/
    Body: {"action": "publish"} or {"action": "unpublish"}
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk):
        sheet = get_object_or_404(ResultSheet, pk=pk, school=request.school)
        serializer = PublishResultSheetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']

        if action == 'publish':
            if sheet.is_published:
                return Response(
                    {'detail': 'Result sheet is already published.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Auto-compute positions before publishing
            _recompute_positions(sheet)
            sheet.publish(published_by=request.user)
            return Response({
                'detail': 'Result sheet published successfully.',
                'sheet': ResultSheetSerializer(sheet).data,
            })
        else:  # unpublish
            if not sheet.is_published:
                return Response(
                    {'detail': 'Result sheet is not published.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sheet.unpublish()
            return Response({
                'detail': 'Result sheet unpublished (reverted to draft).',
                'sheet': ResultSheetSerializer(sheet).data,
            })


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT SCORES
# ─────────────────────────────────────────────────────────────────────────────

class ScoreListView(generics.ListAPIView):
    """
    GET /results/sheets/<sheet_id>/scores/
    Optional filters: ?student=<id>&subject=<id>
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    serializer_class = StudentScoreSerializer

    def get_queryset(self):
        sheet = get_object_or_404(
            ResultSheet, pk=self.kwargs['sheet_id'], school=self.request.school
        )
        qs = StudentScore.objects.filter(result_sheet=sheet).select_related(
            'student', 'subject', 'entered_by'
        )
        student_id = self.request.query_params.get('student')
        subject_id = self.request.query_params.get('subject')
        if student_id:
            qs = qs.filter(student_id=student_id)
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        return qs


class ScoreCreateUpdateView(APIView):
    """
    POST /results/sheets/<sheet_id>/scores/
    Create or update a single student score (upsert by student+subject).
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, sheet_id):
        sheet = get_object_or_404(ResultSheet, pk=sheet_id, school=request.school)
        serializer = StudentScoreCreateSerializer(
            data=request.data,
            context={'request': request, 'result_sheet': sheet},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            score, created = StudentScore.objects.update_or_create(
                result_sheet=sheet,
                student=data['student'],
                subject=data['subject'],
                defaults={
                    'ca1_score': data.get('ca1_score', Decimal('0')),
                    'ca2_score': data.get('ca2_score', Decimal('0')),
                    'ca3_score': data.get('ca3_score', Decimal('0')),
                    'exam_score': data.get('exam_score', Decimal('0')),
                    'is_absent': data.get('is_absent', False),
                    'entered_by': request.user,
                },
            )
            # update_or_create triggers save() → compute_scores()

            # Refresh/create report card
            card = _get_or_create_report_card(sheet, data['student'])
            card.recompute()

        return Response(
            StudentScoreSerializer(score).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BulkScoreEntryView(APIView):
    """
    POST /results/sheets/<sheet_id>/scores/bulk/
    Enter scores for multiple students for one subject at once.
    Body:
    {
        "subject": "<uuid>",
        "scores": [
            {"student_id": "<uuid>", "ca1_score": 15, "ca2_score": 12, "exam_score": 45},
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, sheet_id):
        sheet = get_object_or_404(ResultSheet, pk=sheet_id, school=request.school)
        if sheet.is_published:
            return Response(
                {'detail': 'Cannot edit scores on a published result sheet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BulkScoreEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from subjects.models import Subject
        subject = get_object_or_404(Subject, pk=data['subject'], school=request.school)

        try:
            cfg = request.school.grade_config
            ca_max = cfg.ca_max_score
            exam_max = cfg.exam_max_score
        except Exception:
            ca_max = Decimal('40')
            exam_max = Decimal('60')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        created_count = 0
        updated_count = 0
        errors = []
        affected_students = set()

        with transaction.atomic():
            for i, row in enumerate(data['scores']):
                try:
                    student = User.objects.get(pk=row['student_id'])
                except User.DoesNotExist:
                    errors.append({'row': i, 'error': f'Student {row["student_id"]} not found'})
                    continue

                ca1 = Decimal(str(row.get('ca1_score', 0)))
                ca2 = Decimal(str(row.get('ca2_score', 0)))
                ca3 = Decimal(str(row.get('ca3_score', 0)))
                exam = Decimal(str(row.get('exam_score', 0)))
                is_absent = bool(row.get('is_absent', False))

                if (ca1 + ca2 + ca3) > ca_max:
                    errors.append({
                        'row': i,
                        'student': str(student.id),
                        'error': f'Total CA exceeds max ({ca_max})',
                    })
                    continue
                if exam > exam_max:
                    errors.append({
                        'row': i,
                        'student': str(student.id),
                        'error': f'Exam score exceeds max ({exam_max})',
                    })
                    continue

                score, created = StudentScore.objects.update_or_create(
                    result_sheet=sheet,
                    student=student,
                    subject=subject,
                    defaults={
                        'ca1_score': ca1,
                        'ca2_score': ca2,
                        'ca3_score': ca3,
                        'exam_score': exam,
                        'is_absent': is_absent,
                        'entered_by': request.user,
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                affected_students.add(student)

            # Batch: recompute report cards for all affected students
            for student in affected_students:
                card = _get_or_create_report_card(sheet, student)
                card.recompute()

            # Log the batch
            ScoreEntryBatch.objects.create(
                result_sheet=sheet,
                entered_by=request.user,
                subject=subject,
                scores_entered=created_count,
                scores_updated=updated_count,
            )

        return Response({
            'created': created_count,
            'updated': updated_count,
            'errors': errors,
            'total_processed': created_count + updated_count,
        }, status=status.HTTP_200_OK)


class ScoreDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /results/scores/<id>/
    PATCH  /results/scores/<id>/
    DELETE /results/scores/<id>/
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    serializer_class = StudentScoreSerializer

    def get_queryset(self):
        return StudentScore.objects.filter(
            result_sheet__school=self.request.school
        ).select_related('student', 'subject', 'result_sheet', 'entered_by')

    def update(self, request, *args, **kwargs):
        score = self.get_object()
        if score.result_sheet.is_published:
            return Response(
                {'detail': 'Cannot edit scores on a published result sheet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partial = kwargs.pop('partial', False)
        serializer = StudentScoreCreateSerializer(
            score,
            data=request.data,
            partial=partial,
            context={'request': request, 'result_sheet': score.result_sheet},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            for field, value in data.items():
                setattr(score, field, value)
            score.entered_by = request.user
            score.save()  # triggers compute_scores()

            card = _get_or_create_report_card(score.result_sheet, score.student)
            card.recompute()

        return Response(StudentScoreSerializer(score).data)

    def destroy(self, request, *args, **kwargs):
        score = self.get_object()
        if score.result_sheet.is_published:
            return Response(
                {'detail': 'Cannot delete scores on a published result sheet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        student = score.student
        sheet = score.result_sheet
        score.delete()
        # Recompute report card after deletion
        try:
            card = ReportCard.objects.get(result_sheet=sheet, student=student)
            card.recompute()
        except ReportCard.DoesNotExist:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────────────────────────────
# REPORT CARDS
# ─────────────────────────────────────────────────────────────────────────────

class ReportCardListView(generics.ListAPIView):
    """
    GET /results/sheets/<sheet_id>/report-cards/
    Returns all report cards for a result sheet.
    Teachers/admins see all; students see only their own.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]
    serializer_class = ReportCardSerializer

    def get_queryset(self):
        sheet = get_object_or_404(
            ResultSheet, pk=self.kwargs['sheet_id'], school=self.request.school
        )
        membership = self.request.school_membership
        role = membership.role if membership else None

        qs = ReportCard.objects.filter(result_sheet=sheet).select_related(
            'student', 'result_sheet', 'result_sheet__classroom',
            'result_sheet__term', 'result_sheet__term__academic_year',
        ).order_by('class_position', 'student__last_name')

        # Students can only see their own card (and only if published)
        if role == 'student':
            if not sheet.is_published:
                return ReportCard.objects.none()
            return qs.filter(student=self.request.user)

        return qs


class StudentReportCardView(APIView):
    """
    GET /results/report-card/<student_id>/
    Returns all report cards for a student across all terms.
    Students can only access their own; teachers/admins can access any.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        membership = request.school_membership
        role = membership.role if membership else None

        # Students can only view their own
        if role == 'student' and str(request.user.id) != str(student_id):
            return Response(
                {'detail': 'You can only view your own report cards.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = get_object_or_404(User, pk=student_id)

        # Filter by school
        cards = ReportCard.objects.filter(
            result_sheet__school=request.school,
            student=student,
        ).select_related(
            'result_sheet', 'result_sheet__classroom',
            'result_sheet__term', 'result_sheet__term__academic_year',
        ).order_by(
            '-result_sheet__term__academic_year__start_date',
            'result_sheet__term__order',
        )

        # Students only see published cards
        if role == 'student':
            cards = cards.filter(result_sheet__status=ResultSheet.Status.PUBLISHED)

        # Optional term filter
        term_id = request.query_params.get('term')
        if term_id:
            cards = cards.filter(result_sheet__term_id=term_id)

        serializer = ReportCardSerializer(cards, many=True)
        return Response({
            'student_id': str(student_id),
            'student_name': student.full_name,
            'total_terms': cards.count(),
            'report_cards': serializer.data,
        })


class ReportCardDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /results/report-cards/<id>/
    PATCH /results/report-cards/<id>/   — update remarks/attendance
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ReportCardUpdateSerializer
        return ReportCardSerializer

    def get_queryset(self):
        return ReportCard.objects.filter(
            result_sheet__school=self.request.school
        ).select_related(
            'student', 'result_sheet', 'result_sheet__classroom',
            'result_sheet__term',
        )

    def get_object(self):
        obj = super().get_object()
        membership = self.request.school_membership
        role = membership.role if membership else None
        # Students can only see their own published cards
        if role == 'student':
            if obj.student != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You can only view your own report card.')
            if not obj.result_sheet.is_published:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('Results have not been published yet.')
        return obj

    def update(self, request, *args, **kwargs):
        membership = request.school_membership
        role = membership.role if membership else None
        if role not in ('school_admin', 'teacher'):
            return Response(
                {'detail': 'Only teachers and admins can update report cards.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class RecomputeReportCardsView(APIView):
    """
    POST /results/sheets/<sheet_id>/recompute/
    Recomputes all report cards and positions for a result sheet.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, sheet_id):
        sheet = get_object_or_404(ResultSheet, pk=sheet_id, school=request.school)

        with transaction.atomic():
            # Get all students with scores in this sheet
            student_ids = StudentScore.objects.filter(
                result_sheet=sheet
            ).values_list('student_id', flat=True).distinct()

            from django.contrib.auth import get_user_model
            User = get_user_model()
            students = User.objects.filter(id__in=student_ids)

            for student in students:
                card = _get_or_create_report_card(sheet, student)
                card.recompute()

            _recompute_positions(sheet)

        return Response({
            'detail': f'Recomputed report cards for {students.count()} students.',
            'students_processed': students.count(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# CLASS RESULT SHEET  (full grid view)
# ─────────────────────────────────────────────────────────────────────────────

class ClassResultSheetView(APIView):
    """
    GET /results/class/<classroom_id>/
    Returns the full result grid for a classroom (all students × all subjects).
    Optional: ?term=<id>
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get(self, request, classroom_id):
        from schools.models import ClassRoom
        classroom = get_object_or_404(ClassRoom, pk=classroom_id, school=request.school)

        term_id = request.query_params.get('term')
        if term_id:
            sheet = get_object_or_404(
                ResultSheet, classroom=classroom, term_id=term_id, school=request.school
            )
        else:
            sheet = ResultSheet.objects.filter(
                classroom=classroom, school=request.school
            ).order_by('-created_at').first()
            if not sheet:
                return Response(
                    {'detail': 'No result sheet found for this classroom.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # All subjects in this sheet
        from subjects.models import Subject
        subject_ids = StudentScore.objects.filter(
            result_sheet=sheet
        ).values_list('subject_id', flat=True).distinct()
        subjects = Subject.objects.filter(id__in=subject_ids).order_by('name')

        # All students with scores
        from django.contrib.auth import get_user_model
        User = get_user_model()
        student_ids = StudentScore.objects.filter(
            result_sheet=sheet
        ).values_list('student_id', flat=True).distinct()
        students = User.objects.filter(id__in=student_ids).order_by('last_name', 'first_name')

        # Build grid
        rows = []
        for student in students:
            scores = {
                str(s.subject_id): s
                for s in StudentScore.objects.filter(
                    result_sheet=sheet, student=student
                ).select_related('subject')
            }
            try:
                card = ReportCard.objects.get(result_sheet=sheet, student=student)
                position = card.class_position
                average = card.average_score
            except ReportCard.DoesNotExist:
                position = None
                average = None

            row = {
                'student_id': str(student.id),
                'student_name': student.full_name,
                'position': position,
                'average': average,
                'subjects': {},
            }
            for subj in subjects:
                score = scores.get(str(subj.id))
                row['subjects'][subj.code] = {
                    'total': str(score.total_score) if score else None,
                    'grade': score.grade if score else None,
                    'percentage': str(score.percentage) if score else None,
                } if score else None
            rows.append(row)

        # Sort by position
        rows.sort(key=lambda r: (r['position'] or 9999, r['student_name']))

        return Response({
            'result_sheet_id': str(sheet.id),
            'classroom': classroom.name,
            'term': sheet.term.name,
            'status': sheet.status,
            'subjects': [{'id': str(s.id), 'code': s.code, 'name': s.name} for s in subjects],
            'students': rows,
        })


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class ClassAnalyticsView(APIView):
    """
    GET /results/analytics/class/<sheet_id>/
    Returns per-subject analytics + top students + overall stats.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get(self, request, sheet_id):
        sheet = get_object_or_404(ResultSheet, pk=sheet_id, school=request.school)

        try:
            pass_mark = request.school.grade_config.pass_mark
        except Exception:
            pass_mark = Decimal('40.00')

        # Per-subject analytics
        from subjects.models import Subject
        subject_ids = StudentScore.objects.filter(
            result_sheet=sheet, is_absent=False
        ).values_list('subject_id', flat=True).distinct()
        subjects = Subject.objects.filter(id__in=subject_ids)

        subject_analytics = []
        for subj in subjects:
            scores = StudentScore.objects.filter(
                result_sheet=sheet, subject=subj, is_absent=False
            )
            agg = scores.aggregate(
                highest=Max('percentage'),
                lowest=Min('percentage'),
                average=Avg('percentage'),
                total=Count('id'),
                passed=Count('id', filter=Q(percentage__gte=pass_mark)),
            )
            total = agg['total'] or 0
            passed = agg['passed'] or 0
            failed = total - passed
            pass_rate = (
                Decimal(str(passed / total * 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if total > 0 else Decimal('0.00')
            )

            # Grade distribution
            grade_dist = {}
            for score in scores.values('grade'):
                g = score['grade']
                grade_dist[g] = grade_dist.get(g, 0) + 1

            subject_analytics.append({
                'subject_id': str(subj.id),
                'subject_name': subj.name,
                'subject_code': subj.code,
                'students_scored': total,
                'highest_score': agg['highest'] or Decimal('0'),
                'lowest_score': agg['lowest'] or Decimal('0'),
                'average_score': (agg['average'] or Decimal('0')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                ),
                'pass_count': passed,
                'fail_count': failed,
                'pass_rate': pass_rate,
                'grade_distribution': grade_dist,
            })

        # Overall class stats from ReportCards
        cards_agg = ReportCard.objects.filter(result_sheet=sheet).aggregate(
            total_students=Count('id'),
            class_avg=Avg('average_score'),
        )
        total_students = cards_agg['total_students'] or 0
        class_average = (cards_agg['class_avg'] or Decimal('0')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Overall pass rate: students who passed ALL subjects
        all_scores_count = StudentScore.objects.filter(
            result_sheet=sheet, is_absent=False
        ).count()
        passed_scores_count = StudentScore.objects.filter(
            result_sheet=sheet, is_absent=False, percentage__gte=pass_mark
        ).count()
        overall_pass_rate = (
            Decimal(str(passed_scores_count / all_scores_count * 100)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ) if all_scores_count > 0 else Decimal('0.00')
        )

        # Top 5 students
        top_cards = ReportCard.objects.filter(result_sheet=sheet).order_by(
            '-average_score'
        ).select_related('student')[:5]
        top_students = [
            {
                'student_id': str(c.student.id),
                'student_name': c.student.full_name,
                'average_score': str(c.average_score),
                'position': c.class_position,
            }
            for c in top_cards
        ]

        return Response({
            'result_sheet_id': str(sheet.id),
            'classroom_name': sheet.classroom.name,
            'term_name': sheet.term.name,
            'total_students': total_students,
            'class_average': class_average,
            'overall_pass_rate': overall_pass_rate,
            'subjects': subject_analytics,
            'top_students': top_students,
        })


class StudentTrendView(APIView):
    """
    GET /results/analytics/student/<student_id>/trend/
    Returns a student's performance trend across all available terms.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        membership = request.school_membership
        role = membership.role if membership else None

        # Students can only view their own trend
        if role == 'student' and str(request.user.id) != str(student_id):
            return Response(
                {'detail': 'You can only view your own performance trend.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = get_object_or_404(User, pk=student_id)

        cards = ReportCard.objects.filter(
            result_sheet__school=request.school,
            student=student,
        ).select_related(
            'result_sheet__term',
            'result_sheet__term__academic_year',
            'result_sheet__classroom',
        ).order_by(
            'result_sheet__term__academic_year__start_date',
            'result_sheet__term__order',
        )

        # Students only see published
        if role == 'student':
            cards = cards.filter(result_sheet__status=ResultSheet.Status.PUBLISHED)

        terms = []
        for card in cards:
            term_data = {
                'term_id': str(card.result_sheet.term.id),
                'term_name': card.result_sheet.term.name,
                'academic_year': card.result_sheet.term.academic_year.name,
                'classroom': card.result_sheet.classroom.name,
                'average_score': str(card.average_score),
                'total_score': str(card.total_score),
                'class_position': card.class_position,
                'out_of': card.out_of,
                'subjects_passed': card.subjects_passed,
                'subjects_failed': card.subjects_failed,
            }
            terms.append(term_data)

        return Response({
            'student_id': str(student_id),
            'student_name': student.full_name,
            'terms': terms,
        })


# ─────────────────────────────────────────────────────────────────────────────
# SCORE ENTRY BATCH LOG
# ─────────────────────────────────────────────────────────────────────────────

class ScoreEntryBatchListView(generics.ListAPIView):
    """
    GET /results/sheets/<sheet_id>/batches/
    Returns audit log of score entry batches for a result sheet.
    """
    permission_classes = [IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    serializer_class = ScoreEntryBatchSerializer

    def get_queryset(self):
        sheet = get_object_or_404(
            ResultSheet, pk=self.kwargs['sheet_id'], school=self.request.school
        )
        return ScoreEntryBatch.objects.filter(
            result_sheet=sheet
        ).select_related('entered_by', 'subject').order_by('-created_at')
