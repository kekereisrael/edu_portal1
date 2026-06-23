"""
URL configuration for the results app.
"""

from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    # ── Grade Configuration ───────────────────────────────────────────────────
    # GET/PUT/PATCH  /api/v1/results/grade-config/
    path('grade-config/', views.GradeConfigView.as_view(), name='grade-config'),
    # POST           /api/v1/results/grade-config/reset-nigerian/
    path(
        'grade-config/reset-nigerian/',
        views.GradeConfigNigerianResetView.as_view(),
        name='grade-config-reset-nigerian',
    ),

    # ── Result Sheets ─────────────────────────────────────────────────────────
    # GET/POST       /api/v1/results/sheets/
    path('sheets/', views.ResultSheetListCreateView.as_view(), name='sheet-list'),
    # GET/PATCH/DEL  /api/v1/results/sheets/<id>/
    path('sheets/<uuid:pk>/', views.ResultSheetDetailView.as_view(), name='sheet-detail'),
    # POST           /api/v1/results/sheets/<id>/publish/
    path(
        'sheets/<uuid:pk>/publish/',
        views.PublishResultSheetView.as_view(),
        name='sheet-publish',
    ),
    # POST           /api/v1/results/sheets/<id>/recompute/
    path(
        'sheets/<uuid:sheet_id>/recompute/',
        views.RecomputeReportCardsView.as_view(),
        name='sheet-recompute',
    ),

    # ── Scores ────────────────────────────────────────────────────────────────
    # GET            /api/v1/results/sheets/<id>/scores/
    path(
        'sheets/<uuid:sheet_id>/scores/',
        views.ScoreListView.as_view(),
        name='score-list',
    ),
    # POST           /api/v1/results/sheets/<id>/scores/entry/
    path(
        'sheets/<uuid:sheet_id>/scores/entry/',
        views.ScoreCreateUpdateView.as_view(),
        name='score-entry',
    ),
    # POST           /api/v1/results/sheets/<id>/scores/bulk/
    path(
        'sheets/<uuid:sheet_id>/scores/bulk/',
        views.BulkScoreEntryView.as_view(),
        name='score-bulk',
    ),
    # GET/PATCH/DEL  /api/v1/results/scores/<id>/
    path('scores/<uuid:pk>/', views.ScoreDetailView.as_view(), name='score-detail'),

    # ── Report Cards ──────────────────────────────────────────────────────────
    # GET            /api/v1/results/sheets/<id>/report-cards/
    path(
        'sheets/<uuid:sheet_id>/report-cards/',
        views.ReportCardListView.as_view(),
        name='report-card-list',
    ),
    # GET/PATCH      /api/v1/results/report-cards/<id>/
    path(
        'report-cards/<uuid:pk>/',
        views.ReportCardDetailView.as_view(),
        name='report-card-detail',
    ),
    # GET            /api/v1/results/report-card/<student_id>/
    path(
        'report-card/<uuid:student_id>/',
        views.StudentReportCardView.as_view(),
        name='student-report-card',
    ),

    # ── Class Result Grid ─────────────────────────────────────────────────────
    # GET            /api/v1/results/class/<classroom_id>/
    path(
        'class/<uuid:classroom_id>/',
        views.ClassResultSheetView.as_view(),
        name='class-result-sheet',
    ),

    # ── Analytics ─────────────────────────────────────────────────────────────
    # GET            /api/v1/results/analytics/class/<sheet_id>/
    path(
        'analytics/class/<uuid:sheet_id>/',
        views.ClassAnalyticsView.as_view(),
        name='class-analytics',
    ),
    # GET            /api/v1/results/analytics/student/<student_id>/trend/
    path(
        'analytics/student/<uuid:student_id>/trend/',
        views.StudentTrendView.as_view(),
        name='student-trend',
    ),

    # ── Audit Log ─────────────────────────────────────────────────────────────
    # GET            /api/v1/results/sheets/<id>/batches/
    path(
        'sheets/<uuid:sheet_id>/batches/',
        views.ScoreEntryBatchListView.as_view(),
        name='score-batch-list',
    ),
]
