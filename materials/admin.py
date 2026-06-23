"""
Django admin configuration for the materials app.
"""

from django.contrib import admin
from .models import Material, MaterialProgress, MaterialComment, MaterialBookmark, MaterialRating


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'school', 'subject', 'material_type', 'is_published', 'file_size_display', 'uploaded_by', 'created_at']
    list_filter = ['school', 'material_type', 'is_published', 'subject']
    search_fields = ['title', 'description', 'subject__name']
    readonly_fields = ['file_size_bytes', 'file_size_display', 'created_at', 'updated_at']
    actions = ['publish_materials', 'unpublish_materials']

    def publish_materials(self, request, queryset):
        count = queryset.update(is_published=True)
        self.message_user(request, f'{count} material(s) published.')
    publish_materials.short_description = 'Publish selected materials'

    def unpublish_materials(self, request, queryset):
        count = queryset.update(is_published=False)
        self.message_user(request, f'{count} material(s) unpublished.')
    unpublish_materials.short_description = 'Unpublish selected materials'


@admin.register(MaterialProgress)
class MaterialProgressAdmin(admin.ModelAdmin):
    list_display = ['student', 'material', 'progress_percent', 'completed', 'last_accessed_at']
    list_filter = ['completed', 'material__school']
    search_fields = ['student__email', 'material__title']
    readonly_fields = ['last_accessed_at']


@admin.register(MaterialComment)
class MaterialCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'material', 'content_short', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'material__school']
    search_fields = ['user__email', 'material__title', 'content']

    def content_short(self, obj):
        return obj.content[:80]
    content_short.short_description = 'Content'


@admin.register(MaterialBookmark)
class MaterialBookmarkAdmin(admin.ModelAdmin):
    list_display = ['student', 'material', 'created_at']
    list_filter = ['material__school']
    search_fields = ['student__email', 'material__title']


@admin.register(MaterialRating)
class MaterialRatingAdmin(admin.ModelAdmin):
    list_display = ['student', 'material', 'rating', 'created_at']
    list_filter = ['rating', 'material__school']
    search_fields = ['student__email', 'material__title']
