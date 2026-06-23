"""
URL configuration for the schools app.
"""

from django.urls import path

from . import views

app_name = 'schools'

urlpatterns = [
    # ── School CRUD ───────────────────────────────────────────────────────────
    path('', views.SchoolListView.as_view(), name='school_list'),
    path('create/', views.SchoolCreateView.as_view(), name='school_create'),
    path('current/', views.SchoolDetailView.as_view(), name='school_detail'),

    # ── School Profile (combined school + settings edit) ─────────────────────
    path('profile/', views.SchoolProfileView.as_view(), name='school_profile'),

    # ── School Settings ───────────────────────────────────────────────────────
    path('settings/', views.SchoolSettingsView.as_view(), name='school_settings'),

    # ── Members ───────────────────────────────────────────────────────────────
    path('members/', views.MemberListView.as_view(), name='member_list'),
    path('members/add/', views.AddMemberView.as_view(), name='add_member'),
    path('members/<uuid:membership_id>/remove/', views.RemoveMemberView.as_view(), name='remove_member'),

    # ── Academic Sessions (new) ───────────────────────────────────────────────
    path('academic-sessions/', views.AcademicSessionListCreateView.as_view(), name='academic_session_list'),
    path('academic-sessions/<uuid:pk>/', views.AcademicSessionDetailView.as_view(), name='academic_session_detail'),
    path('academic-sessions/<uuid:pk>/set-current/', views.SetCurrentSessionView.as_view(), name='set_current_session'),

    # ── Academic Years (legacy) ───────────────────────────────────────────────
    path('academic-years/', views.AcademicYearListCreateView.as_view(), name='academic_year_list'),
    path('academic-years/<uuid:pk>/', views.AcademicYearDetailView.as_view(), name='academic_year_detail'),
    path('academic-years/<uuid:academic_year_id>/terms/', views.TermListCreateView.as_view(), name='term_list'),

    # ── Departments ───────────────────────────────────────────────────────────
    path('departments/', views.DepartmentListCreateView.as_view(), name='department_list'),
    path('departments/<uuid:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),

    # ── Class Levels (JSS1–SSS3) ──────────────────────────────────────────────
    path('class-levels/', views.ClassLevelListView.as_view(), name='class_level_list'),
    path('class-levels/<uuid:pk>/', views.ClassLevelDetailView.as_view(), name='class_level_detail'),

    # ── Classrooms ────────────────────────────────────────────────────────────
    path('classrooms/', views.ClassRoomListCreateView.as_view(), name='classroom_list'),
    path('classrooms/<uuid:pk>/', views.ClassRoomDetailView.as_view(), name='classroom_detail'),
    path('classrooms/<uuid:pk>/students/', views.ClassRoomStudentsView.as_view(), name='classroom_students'),
    path('classrooms/<uuid:pk>/assign-teacher/', views.AssignTeacherView.as_view(), name='assign_teacher'),
    path('classrooms/<uuid:pk>/remove-teacher/', views.RemoveTeacherView.as_view(), name='remove_teacher'),

    # ── Subject ↔ Class assignment (TASK 4) ───────────────────────────────────
    path('classrooms/<uuid:pk>/subjects/', views.ClassSubjectListView.as_view(), name='class_subject_list'),
    path('classrooms/<uuid:pk>/subjects/assign/', views.AssignSubjectToClassView.as_view(), name='assign_subject_to_class'),
    path('classrooms/<uuid:pk>/subjects/<uuid:subject_id>/assign-teacher/', views.AssignTeacherToSubjectView.as_view(), name='assign_teacher_to_subject'),

    # ── Student Enrollment (TASK 5) ───────────────────────────────────────────
    path('enrollments/', views.StudentEnrollmentListView.as_view(), name='enrollment_list'),
    path('enrollments/enroll/', views.EnrollStudentView.as_view(), name='enroll_student'),
    path('enrollments/bulk-enroll/', views.BulkEnrollView.as_view(), name='bulk_enroll'),
    path('enrollments/<uuid:pk>/', views.StudentEnrollmentDetailView.as_view(), name='enrollment_detail'),
    path('enrollments/<uuid:pk>/update-status/', views.StudentClassAssignmentStatusView.as_view(), name='enrollment_update_status'),

    # ══ PHASE 7A — School Registration & Onboarding ═══════════════════════════
    # POST   /api/v1/schools/register/                         — start registration
    # GET    /api/v1/schools/register/<id>/                    — check status
    # POST   /api/v1/schools/register/verify-email/            — verify email token
    # POST   /api/v1/schools/register/<id>/resend-verification/ — resend email
    # POST   /api/v1/schools/register/<id>/onboarding/step-1/  — basic info
    # POST   /api/v1/schools/register/<id>/onboarding/step-2/  — logo & branding
    # POST   /api/v1/schools/register/<id>/onboarding/step-3/  — academic setup
    # POST   /api/v1/schools/register/<id>/onboarding/step-4/  — admin account
    # POST   /api/v1/schools/register/<id>/complete/           — activate school
    path('register/', views.SchoolRegistrationInitView.as_view(), name='registration_init'),
    path('register/verify-email/', views.VerifySchoolEmailView.as_view(), name='verify_email'),
    path('register/<uuid:registration_id>/', views.SchoolRegistrationStatusView.as_view(), name='registration_status'),
    path('register/<uuid:registration_id>/resend-verification/', views.ResendVerificationEmailView.as_view(), name='resend_verification'),
    path('register/<uuid:registration_id>/onboarding/step-1/', views.OnboardingStep1View.as_view(), name='onboarding_step1'),
    path('register/<uuid:registration_id>/onboarding/step-2/', views.OnboardingStep2View.as_view(), name='onboarding_step2'),
    path('register/<uuid:registration_id>/onboarding/step-3/', views.OnboardingStep3View.as_view(), name='onboarding_step3'),
    path('register/<uuid:registration_id>/onboarding/step-4/', views.OnboardingStep4View.as_view(), name='onboarding_step4'),
    path('register/<uuid:registration_id>/complete/', views.CompleteRegistrationView.as_view(), name='registration_complete'),

    # ══ PHASE 7A — School Admin Dashboard ═════════════════════════════════════
    # GET    /api/v1/schools/dashboard/   — aggregated school stats for admin
    path('dashboard/', views.SchoolDashboardView.as_view(), name='school_dashboard'),

    # ══ PHASE 7A — Member Management by Role ══════════════════════════════════
    # GET    /api/v1/schools/members/students/  — list students
    # GET    /api/v1/schools/members/teachers/  — list teachers + admins
    # POST   /api/v1/schools/members/invite/    — invite staff via email
    path('members/students/', views.SchoolStudentsListView.as_view(), name='member_students'),
    path('members/teachers/', views.SchoolTeachersListView.as_view(), name='member_teachers'),
    path('members/invite/', views.InviteStaffView.as_view(), name='invite_staff'),

    # ══ PHASE 7A — Teacher Management ═════════════════════════════════════════
    # GET    /api/v1/schools/teachers/                                — list teachers
    # POST   /api/v1/schools/teachers/                                — create/invite teacher
    # GET    /api/v1/schools/teachers/<id>/                           — teacher detail
    # PATCH  /api/v1/schools/teachers/<id>/                           — update teacher
    # DELETE /api/v1/schools/teachers/<id>/                           — deactivate teacher
    # POST   /api/v1/schools/teachers/<id>/assign-subject/            — assign subject
    # DELETE /api/v1/schools/teachers/<id>/remove-subject/            — remove subject
    path('teachers/', views.TeacherListCreateView.as_view(), name='teacher_list'),
    path('teachers/<uuid:membership_id>/', views.TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<uuid:membership_id>/assign-subject/', views.TeacherAssignSubjectView.as_view(), name='teacher_assign_subject'),
    path('teachers/<uuid:membership_id>/remove-subject/', views.TeacherRemoveSubjectView.as_view(), name='teacher_remove_subject'),

    # ══ PHASE 7A — Student Management ═════════════════════════════════════════
    # GET    /api/v1/schools/students/                                — list students
    # POST   /api/v1/schools/students/                                — create student
    # POST   /api/v1/schools/students/bulk-upload/                    — bulk upload
    # GET    /api/v1/schools/students/<id>/                           — student detail
    # PATCH  /api/v1/schools/students/<id>/                           — update student
    # DELETE /api/v1/schools/students/<id>/                           — deactivate student
    path('students/', views.StudentListCreateView.as_view(), name='student_list'),
    path('students/bulk-upload/', views.StudentBulkUploadView.as_view(), name='student_bulk_upload'),
    path('students/<uuid:membership_id>/', views.StudentDetailView.as_view(), name='student_detail'),

    # ══ PHASE 7B — TASK 1: Platform Landing Page API ═══════════════════════════
    # GET  /api/v1/schools/platform/info/       — platform features + pricing
    # POST /api/v1/schools/platform/book-demo/  — book a demo
    path('platform/info/', views.PlatformInfoView.as_view(), name='platform_info'),
    path('platform/book-demo/', views.BookDemoView.as_view(), name='book_demo'),

    # ══ PHASE 7B — TASK 2: Registration Review ════════════════════════════════
    # GET /api/v1/schools/register/<id>/review/  — review all onboarding data
    path('register/<uuid:registration_id>/review/', views.RegistrationReviewView.as_view(), name='registration_review'),

    # ══ PHASE 7B — TASK 3: Enhanced Dashboard ════════════════════════════════
    # GET /api/v1/schools/dashboard/enhanced/  — rich stats + quick actions + activity
    path('dashboard/enhanced/', views.EnhancedSchoolDashboardView.as_view(), name='enhanced_dashboard'),

    # ══ PHASE 7B — TASK 4: Bulk Import ════════════════════════════════════════
    # POST /api/v1/schools/import/               — upload CSV/Excel file
    # GET  /api/v1/schools/import/template/      — download CSV template
    path('import/', views.BulkImportView.as_view(), name='bulk_import'),
    path('import/template/', views.BulkImportTemplateView.as_view(), name='bulk_import_template'),

    # ══ PHASE 7B — TASK 5: Class Promotion Engine ═════════════════════════════
    # POST /api/v1/schools/promotions/preview/          — dry-run preview
    # POST /api/v1/schools/promotions/apply/            — apply promotion
    # GET  /api/v1/schools/promotions/                  — list all promotions
    # POST /api/v1/schools/promotions/<id>/undo/        — undo a promotion
    path('promotions/', views.PromotionReportView.as_view(), name='promotion_report'),
    path('promotions/preview/', views.PromotionPreviewView.as_view(), name='promotion_preview'),
    path('promotions/apply/', views.PromotionApplyView.as_view(), name='promotion_apply'),
    path('promotions/<uuid:promotion_id>/undo/', views.PromotionUndoView.as_view(), name='promotion_undo'),

    # ══ PHASE 7B — TASK 6: School Branding Engine ═════════════════════════════
    # GET   /api/v1/schools/branding/  — retrieve branding context
    # PATCH /api/v1/schools/branding/  — update branding fields
    path('branding/', views.SchoolBrandingView.as_view(), name='school_branding'),

    # ══ PHASE 7B — TASK 7: Document Generator ═════════════════════════════════
    # GET /api/v1/schools/documents/id-card/<student_id>/
    # GET /api/v1/schools/documents/result-sheet/<student_id>/
    # GET /api/v1/schools/documents/report-card/<student_id>/
    # GET /api/v1/schools/documents/exam-slip/<student_id>/
    # GET /api/v1/schools/documents/certificate/<student_id>/
    # All support ?format=pdf for PDF download
    path('documents/id-card/<uuid:student_id>/', views.StudentIDCardView.as_view(), name='document_id_card'),
    path('documents/result-sheet/<uuid:student_id>/', views.ResultSheetView.as_view(), name='document_result_sheet'),
    path('documents/report-card/<uuid:student_id>/', views.ReportCardView.as_view(), name='document_report_card'),
    path('documents/exam-slip/<uuid:student_id>/', views.ExamSlipView.as_view(), name='document_exam_slip'),
    path('documents/certificate/<uuid:student_id>/', views.CertificateView.as_view(), name='document_certificate'),

    # ══ PHASE 7B — TASK 8: Audit Logs ═════════════════════════════════════════
    # GET /api/v1/schools/audit-logs/  — paginated audit trail
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),

    # ══ PHASE 7B — TASK 9: School Settings Module ═════════════════════════════
    # GET   /api/v1/schools/settings/full/     — full school settings
    # PATCH /api/v1/schools/settings/full/     — update school info + settings
    # GET   /api/v1/schools/settings/grading/  — grading scale + pass mark
    # PUT   /api/v1/schools/settings/grading/  — replace grading scale
    path('settings/full/', views.SchoolSettingsDetailView.as_view(), name='settings_full'),
    path('settings/grading/', views.GradingScaleView.as_view(), name='settings_grading'),
]
