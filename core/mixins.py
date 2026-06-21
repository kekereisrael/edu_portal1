"""
Core mixins for views and serializers.
"""

from rest_framework import permissions


class SchoolQuerysetMixin:
    """
    Mixin that auto-filters querysets by the current school context.
    Use in all school-scoped views.
    """

    school_field = 'school'
    select_related_fields = []
    prefetch_related_fields = []

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, 'school') and self.request.school:
            qs = qs.filter(**{self.school_field: self.request.school})
        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)
        if self.prefetch_related_fields:
            qs = qs.prefetch_related(*self.prefetch_related_fields)
        return qs


class SchoolCreateMixin:
    """
    Mixin that auto-assigns the current school on object creation.
    """

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class DynamicFieldsMixin:
    """
    Serializer mixin that allows clients to request specific fields.
    Usage: GET /api/v1/subjects/?fields=id,name,code
    """

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request:
            requested = request.query_params.get('fields')
            if requested:
                allowed = set(requested.split(','))
                fields = {k: v for k, v in fields.items() if k in allowed}
        return fields
