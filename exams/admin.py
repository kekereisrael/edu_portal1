"""
Django admin configuration for the exams app.
"""

from django.contrib import admin

from .models import (
    QuestionBank, QuestionTag, Exam, ExamTemplate, ExamGroup,
    Question, QuestionOption, ExamAttempt, Answer, Result,
)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 4
    fields = ['text', 'is_correct', 'order']


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ['question_type', 'text', 'marks', 'order']
    show_change_link = True


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'school', 'subject', 'term', 'exam_type', 'is_published', 'total_marks']
    list_filter = ['school', 'exam_type', 'is_published', 'term']
    search_fields = ['title', 'description']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text_short', 'exam', 'question_type', 'marks', 'order']
    list_filter = ['question_type', 'exam__school']
    search_fields = ['text']
    inlines = [QuestionOptionInline]

    def text_short(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    text_short.short_description = 'Question'


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'subject', 'question_count', 'created_by']
    list_filter = ['school', 'subject']
    search_fields = ['name']


@admin.register(QuestionTag)
class QuestionTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'tag_type', 'school']
    list_filter = ['tag_type', 'school']


@admin.register(ExamTemplate)
class ExamTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'subject', 'created_by']
    list_filter = ['school']


@admin.register(ExamGroup)
class ExamGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'term']
    list_filter = ['school', 'term']


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'attempt_number', 'status', 'score', 'percentage', 'started_at']
    list_filter = ['school', 'status', 'exam']
    search_fields = ['student__email', 'exam__title']


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'is_correct', 'marks_awarded']
    list_filter = ['is_correct', 'attempt__school']


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'term', 'score', 'grade', 'is_published']
    list_filter = ['school', 'term', 'subject', 'is_published', 'grade']
    search_fields = ['student__email', 'subject__name']
