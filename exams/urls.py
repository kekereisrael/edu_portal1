"""
URL configuration for the exams app.
Phase 6B additions: Question Bank, Import, Search, Exam Generation.
Phase 6C additions: Practice Mode, Mock Exams, Weak Topic Detection, Recommendations.
"""

from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    # ── Exams CRUD ────────────────────────────────────────────────────────────
    path('', views.ExamListCreateView.as_view(), name='exam_list'),
    path('<uuid:pk>/', views.ExamDetailView.as_view(), name='exam_detail'),
    path('<uuid:pk>/publish/', views.ExamPublishView.as_view(), name='exam_publish'),

    # ── Questions (exam-scoped) ───────────────────────────────────────────────
    path('<uuid:exam_id>/questions/', views.QuestionListCreateView.as_view(), name='question_list'),
    path('questions/<uuid:pk>/', views.QuestionDetailView.as_view(), name='question_detail'),

    # ── CBT Exam Attempts ─────────────────────────────────────────────────────
    path('<uuid:pk>/start/', views.StartExamView.as_view(), name='start_exam'),
    path('attempts/<uuid:attempt_id>/save/', views.SaveAnswerView.as_view(), name='save_answer'),
    path('attempts/<uuid:attempt_id>/submit/', views.SubmitExamView.as_view(), name='submit_exam'),
    path('<uuid:exam_id>/attempts/', views.ExamAttemptsListView.as_view(), name='exam_attempts'),
    path('attempts/my/', views.MyAttemptsView.as_view(), name='my_attempts'),
    path('attempts/<uuid:pk>/', views.AttemptDetailView.as_view(), name='attempt_detail'),

    # ── Results ───────────────────────────────────────────────────────────────
    path('<uuid:exam_id>/results/', views.ExamResultListView.as_view(), name='exam_results'),
    path('results/my/', views.MyResultsView.as_view(), name='my_results'),

    # ── Bank questions linked to an exam ──────────────────────────────────────
    path('<uuid:exam_id>/bank-questions/', views.ExamBankQuestionListView.as_view(), name='exam_bank_questions'),

    # ── Exam Categories (WAEC, NECO, JAMB, etc.) ──────────────────────────────
    path('bank/exam-categories/', views.ExamCategoryListView.as_view(), name='exam_category_list'),

    # ── Question Categories ───────────────────────────────────────────────────
    path('bank/categories/', views.QuestionCategoryListCreateView.as_view(), name='question_category_list'),
    path('bank/categories/<uuid:pk>/', views.QuestionCategoryDetailView.as_view(), name='question_category_detail'),

    # ── Question Tags ─────────────────────────────────────────────────────────
    path('bank/tags/', views.QuestionTagListCreateView.as_view(), name='question_tag_list'),
    path('bank/tags/<uuid:pk>/', views.QuestionTagDetailView.as_view(), name='question_tag_detail'),

    # ── Question Banks ────────────────────────────────────────────────────────
    path('bank/', views.QuestionBankListCreateView.as_view(), name='question_bank_list'),
    path('bank/<uuid:pk>/', views.QuestionBankDetailView.as_view(), name='question_bank_detail'),

    # ── Bank Questions (with search & filter) ─────────────────────────────────
    path('bank/<uuid:bank_id>/questions/', views.BankQuestionListCreateView.as_view(), name='bank_question_list'),
    path('bank/questions/<uuid:pk>/', views.BankQuestionDetailView.as_view(), name='bank_question_detail'),

    # ── Import ────────────────────────────────────────────────────────────────
    path('bank/<uuid:bank_id>/import/', views.QuestionImportView.as_view(), name='question_import'),
    path('bank/<uuid:bank_id>/import/json/', views.QuestionBulkJSONImportView.as_view(), name='question_import_json'),

    # ── Generate Exam from Bank ───────────────────────────────────────────────
    path('bank/generate-exam/', views.GenerateExamFromBankView.as_view(), name='generate_exam_from_bank'),

    # ══ PHASE 6C ══════════════════════════════════════════════════════════════

    # ── TASK 1: Practice Mode ─────────────────────────────────────────────────
    # POST  /api/v1/exams/practice/start/              — start a new practice session
    # GET   /api/v1/exams/practice/my/                 — list my practice sessions
    # GET   /api/v1/exams/practice/<id>/               — session detail + answers
    # POST  /api/v1/exams/practice/<id>/answer/        — submit one answer (instant feedback)
    # POST  /api/v1/exams/practice/<id>/complete/      — mark session complete
    path('practice/start/', views.StartPracticeView.as_view(), name='practice_start'),
    path('practice/my/', views.MyPracticeSessionsView.as_view(), name='practice_my'),
    path('practice/<uuid:pk>/', views.PracticeSessionDetailView.as_view(), name='practice_detail'),
    path('practice/<uuid:session_id>/answer/', views.SubmitPracticeAnswerView.as_view(), name='practice_answer'),
    path('practice/<uuid:session_id>/complete/', views.CompletePracticeView.as_view(), name='practice_complete'),

    # ── TASK 2: Mock Exam Mode ────────────────────────────────────────────────
    # POST  /api/v1/exams/mock/start/                  — start a new mock exam
    # GET   /api/v1/exams/mock/my/                     — list my mock sessions
    # GET   /api/v1/exams/mock/<id>/                   — session detail (+ answers if submitted)
    # POST  /api/v1/exams/mock/<id>/save/              — save a single answer (no feedback)
    # POST  /api/v1/exams/mock/<id>/submit/            — submit + get full score summary
    path('mock/start/', views.StartMockExamView.as_view(), name='mock_start'),
    path('mock/my/', views.MyMockExamSessionsView.as_view(), name='mock_my'),
    path('mock/<uuid:pk>/', views.MockExamSessionDetailView.as_view(), name='mock_detail'),
    path('mock/<uuid:session_id>/save/', views.SaveMockAnswerView.as_view(), name='mock_save_answer'),
    path('mock/<uuid:session_id>/submit/', views.SubmitMockExamView.as_view(), name='mock_submit'),

    # ── TASK 3: Weak Topic Detection ──────────────────────────────────────────
    # GET   /api/v1/exams/performance/topics/          — all topic performances (weakest first)
    # GET   /api/v1/exams/performance/topics/weak/     — only weak topics
    # GET   /api/v1/exams/performance/topics/strong/   — only strong topics
    # GET   /api/v1/exams/performance/subjects/<id>/   — subject breakdown
    path('performance/topics/', views.MyTopicPerformanceView.as_view(), name='topic_performance'),
    path('performance/topics/weak/', views.WeakTopicsView.as_view(), name='weak_topics'),
    path('performance/topics/strong/', views.StrongTopicsView.as_view(), name='strong_topics'),
    path('performance/subjects/<uuid:subject_id>/', views.SubjectPerformanceBreakdownView.as_view(), name='subject_breakdown'),

    # ── TASK 4: Study Recommendations ────────────────────────────────────────
    # GET   /api/v1/exams/performance/recommendations/ — personalised recommendations
    path('performance/recommendations/', views.StudyRecommendationsView.as_view(), name='recommendations'),
]
