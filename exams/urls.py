"""
URL configuration for the exams app.
"""

from django.urls import path

from . import views

app_name = 'exams'

urlpatterns = [
    # Exams
    path('', views.ExamListCreateView.as_view(), name='exam_list'),
    path('<uuid:pk>/', views.ExamDetailView.as_view(), name='exam_detail'),
    path('<uuid:pk>/publish/', views.ExamPublishView.as_view(), name='exam_publish'),

    # Questions
    path('<uuid:exam_id>/questions/', views.QuestionListCreateView.as_view(), name='question_list'),
    path('questions/<uuid:pk>/', views.QuestionDetailView.as_view(), name='question_detail'),

    # Exam Attempts
    path('<uuid:exam_id>/start/', views.StartExamView.as_view(), name='start_exam'),
    path('attempts/<uuid:attempt_id>/save/', views.SaveAnswerView.as_view(), name='save_answer'),
    path('attempts/<uuid:attempt_id>/submit/', views.SubmitExamView.as_view(), name='submit_exam'),
    path('<uuid:exam_id>/attempts/', views.ExamAttemptListView.as_view(), name='attempt_list'),
    path('attempts/<uuid:pk>/', views.ExamAttemptDetailView.as_view(), name='attempt_detail'),

    # Grading
    path('answers/<uuid:answer_id>/grade/', views.GradeAnswerView.as_view(), name='grade_answer'),

    # Question Banks
    path('question-banks/', views.QuestionBankListCreateView.as_view(), name='question_bank_list'),
    path('question-banks/<uuid:pk>/', views.QuestionBankDetailView.as_view(), name='question_bank_detail'),
    path(
        'question-banks/<uuid:bank_id>/questions/',
        views.QuestionBankQuestionsView.as_view(),
        name='question_bank_questions',
    ),

    # Question Tags
    path('tags/', views.QuestionTagListCreateView.as_view(), name='tag_list'),

    # Exam Templates
    path('templates/', views.ExamTemplateListCreateView.as_view(), name='template_list'),
    path('templates/<uuid:pk>/', views.ExamTemplateDetailView.as_view(), name='template_detail'),

    # Exam Groups
    path('groups/', views.ExamGroupListCreateView.as_view(), name='group_list'),

    # Results
    path('results/', views.ResultListCreateView.as_view(), name='result_list'),
    path('results/<uuid:pk>/', views.ResultDetailView.as_view(), name='result_detail'),
    path('results/publish/', views.PublishResultsView.as_view(), name='publish_results'),
    path('results/my/', views.MyResultsView.as_view(), name='my_results'),
]
