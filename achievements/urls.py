"""
URL configuration for the achievements app.
Phase 6D: Leaderboards, Badges & Achievements, Reports.

All routes are prefixed with /api/v1/achievements/ in config/urls.py.

Leaderboards:
  GET  leaderboard/school/                  — school-wide leaderboard
  GET  leaderboard/class/<classroom_id>/    — class leaderboard
  GET  leaderboard/subject/<subject_id>/    — subject leaderboard
  GET  leaderboard/my-rank/                 — current student's rank
  POST leaderboard/rebuild/                 — force rebuild (admin only)

Badges:
  GET  badges/                              — all available badges
  GET  badges/my/                           — student's earned badges
  POST badges/mark-seen/                    — mark badges as seen

Achievement Page:
  GET  my/                                  — full achievement page

Reports:
  GET  reports/student/                     — student performance report (HTML/PDF)
  GET  reports/subject/                     — subject report
  GET  reports/class/                       — class report (teacher/admin)
  GET  reports/school/                      — school analytics (admin)
"""

from django.urls import path

from achievements.views import (
    # Leaderboards
    SchoolLeaderboardView,
    ClassLeaderboardView,
    SubjectLeaderboardView,
    MyRankView,
    RebuildLeaderboardsView,
    # Badges
    BadgeListView,
    MyBadgesView,
    MarkBadgesSeenView,
    # Achievement Page
    MyAchievementPageView,
    # Reports
    StudentPerformanceReportView,
    SubjectReportView,
    ClassPerformanceReportView,
    SchoolAnalyticsReportView,
)

app_name = 'achievements'

urlpatterns = [
    # ── Leaderboards ──────────────────────────────────────────────────────────
    path('leaderboard/school/', SchoolLeaderboardView.as_view(), name='leaderboard-school'),
    path('leaderboard/class/<uuid:classroom_id>/', ClassLeaderboardView.as_view(), name='leaderboard-class'),
    path('leaderboard/subject/<uuid:subject_id>/', SubjectLeaderboardView.as_view(), name='leaderboard-subject'),
    path('leaderboard/my-rank/', MyRankView.as_view(), name='leaderboard-my-rank'),
    path('leaderboard/rebuild/', RebuildLeaderboardsView.as_view(), name='leaderboard-rebuild'),

    # ── Badges ────────────────────────────────────────────────────────────────
    path('badges/', BadgeListView.as_view(), name='badge-list'),
    path('badges/my/', MyBadgesView.as_view(), name='my-badges'),
    path('badges/mark-seen/', MarkBadgesSeenView.as_view(), name='badges-mark-seen'),

    # ── Achievement Page ──────────────────────────────────────────────────────
    path('my/', MyAchievementPageView.as_view(), name='achievement-page'),

    # ── Reports ───────────────────────────────────────────────────────────────
    path('reports/student/', StudentPerformanceReportView.as_view(), name='report-student'),
    path('reports/subject/', SubjectReportView.as_view(), name='report-subject'),
    path('reports/class/', ClassPerformanceReportView.as_view(), name='report-class'),
    path('reports/school/', SchoolAnalyticsReportView.as_view(), name='report-school'),
]
