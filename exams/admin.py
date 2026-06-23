"""
Admin configuration for the exams app.
Phase 6B additions: ExamCategory, QuestionCategory, QuestionTag,
QuestionBank, BankQuestion, ExamBankQuestion.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Exam, Question, ExamAttempt, ExamAnswer, ExamResult,
    ExamCategory, QuestionCategory, QuestionTag,
    QuestionBank, BankQuestion, ExamBankQuestion,
)


# ─────────────────────────────────────────────────────────────────────────────
# Existing models
# ─────────────────────────────────────────────────────────────────────────────

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ['question_text', 'question_type', 'difficulty', 'marks', 'order', 'is_active']
    readonly_fields = ['created_at']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'school', 'subject', 'exam_type', 'status', 'question_count', 'created_by', 'created_at']
    list_filter = ['status', 'exam_type', 'school']
    search_fields = ['title', 'subject__name', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at', 'total_marks']
    inlines = [QuestionInline]

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.question_count


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'exam', 'question_type', 'difficulty', 'marks', 'is_active']
    list_filter = ['question_type', 'difficulty', 'is_active']
    search_fields = ['question_text', 'exam__title']

    @admin.display(description='Question')
    def question_text_short(self, obj):
        return obj.question_text[:80]


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'status', 'score', 'percentage', 'passed', 'started_at']
    list_filter = ['status', 'passed']
    search_fields = ['student__email', 'exam__title']
    readonly_fields = ['started_at', 'submitted_at']


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'score', 'percentage', 'passed', 'grade', 'rank']
    list_filter = ['passed', 'grade']
    search_fields = ['student__email', 'exam__title']


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6B — Exam Category
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ExamCategory)
class ExamCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_public', 'is_active', 'created_at']
    list_filter = ['is_public', 'is_active']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at']
    ordering = ['name']


# ─────────────────────────────────────────────────────────────────────────────
# Question Category & Tag
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'school']
    search_fields = ['name', 'school__name']
    readonly_fields = ['created_at']


@admin.register(QuestionTag)
class QuestionTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'color_swatch', 'created_at']
    list_filter = ['school']
    search_fields = ['name', 'school__name']
    readonly_fields = ['created_at']

    @admin.display(description='Colour')
    def color_swatch(self, obj):
        return format_html(
            '<span style="background:{};padding:2px 12px;border-radius:4px;">&nbsp;</span> {}',
            obj.color, obj.color,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Question Bank
# ─────────────────────────────────────────────────────────────────────────────

class BankQuestionInline(admin.TabularInline):
    model = BankQuestion
    extra = 0
    fields = ['question_text_short', 'question_type', 'difficulty', 'marks', 'is_active']
    readonly_fields = ['question_text_short', 'created_at']
    show_change_link = True

    @admin.display(description='Question')
    def question_text_short(self, obj):
        return obj.question_text[:80]


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'school', 'subject', 'exam_category',
        'class_level', 'question_count', 'is_shared', 'is_active', 'created_at',
    ]
    list_filter = ['is_active', 'is_shared', 'exam_category', 'school']
    search_fields = ['name', 'school__name', 'subject__name']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['school', 'subject', 'exam_category', 'class_level']
    inlines = [BankQuestionInline]

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.question_count


# ─────────────────────────────────────────────────────────────────────────────
# Bank Question
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(BankQuestion)
class BankQuestionAdmin(admin.ModelAdmin):
    list_display = [
        'question_text_short', 'bank', 'question_type', 'difficulty',
        'marks', 'times_used', 'exam_year', 'is_active', 'created_at',
    ]
    list_filter = ['question_type', 'difficulty', 'is_active', 'exam_category', 'bank__school']
    search_fields = ['question_text', 'bank__name', 'bank__school__name']
    readonly_fields = ['times_used', 'import_source', 'import_batch', 'created_at', 'updated_at']
    filter_horizontal = ['tags']
    list_select_related = ['bank', 'topic', 'exam_category']
    ordering = ['-created_at']
    actions = ['mark_active', 'mark_inactive']

    @admin.display(description='Question')
    def question_text_short(self, obj):
        return obj.question_text[:80]

    @admin.action(description='Mark selected as Active')
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} question(s) marked as active.')

    @admin.action(description='Mark selected as Inactive')
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} question(s) marked as inactive.')

    fieldsets = [
        ('Question Content', {
            'fields': [
                'bank', 'question_text', 'question_type',
                'option_a', 'option_b', 'option_c', 'option_d',
                'correct_answer', 'explanation', 'image',
            ],
        }),
        ('Classification', {
            'fields': ['difficulty', 'marks', 'topic', 'category', 'tags'],
        }),
        ('Exam Association', {
            'fields': ['exam_category', 'exam_year'],
        }),
        ('Metadata', {
            'fields': ['is_active', 'times_used', 'import_source', 'import_batch', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Exam Bank Question (snapshot)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ExamBankQuestion)
class ExamBankQuestionAdmin(admin.ModelAdmin):
    list_display = ['exam', 'question_text_short', 'difficulty', 'marks', 'order', 'is_active']
    list_filter = ['difficulty', 'is_active', 'exam__school']
    search_fields = ['exam__title', 'question_text']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['exam', 'bank_question']

    @admin.display(description='Question')
    def question_text_short(self, obj):
        return obj.question_text[:80]
