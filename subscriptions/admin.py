"""
Admin configuration for the subscriptions app.
"""

from django.contrib import admin

from .models import (
    Plan, PlanFeature, Subscription, SubscriptionHistory,
    AICredit, AddOn, SchoolAddOn,
)


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'price_monthly', 'price_yearly', 'max_students', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']
    inlines = [PlanFeatureInline]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['school', 'plan', 'status', 'billing_cycle', 'current_period_end', 'auto_renew']
    list_filter = ['status', 'plan', 'billing_cycle', 'auto_renew']
    search_fields = ['school__name', 'school__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'action', 'from_plan', 'to_plan', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['subscription__school__name']
    readonly_fields = ['created_at']


@admin.register(AICredit)
class AICreditAdmin(admin.ModelAdmin):
    list_display = ['school', 'balance', 'monthly_allocation', 'last_reset_date']
    search_fields = ['school__name']


@admin.register(AddOn)
class AddOnAdmin(admin.ModelAdmin):
    list_display = ['name', 'addon_type', 'price', 'value', 'is_active']
    list_filter = ['addon_type', 'is_active']


@admin.register(SchoolAddOn)
class SchoolAddOnAdmin(admin.ModelAdmin):
    list_display = ['school', 'addon', 'quantity', 'purchased_at', 'expires_at', 'is_active']
    list_filter = ['is_active', 'addon__addon_type']
    search_fields = ['school__name', 'addon__name']
