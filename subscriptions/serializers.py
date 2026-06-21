"""
Serializers for the subscriptions app.
"""

from rest_framework import serializers

from .models import (
    Plan, PlanFeature, Subscription, SubscriptionHistory,
    AICredit, AddOn, SchoolAddOn,
)


class PlanFeatureSerializer(serializers.ModelSerializer):
    """Serializer for PlanFeature model."""

    class Meta:
        model = PlanFeature
        fields = ['feature_key', 'feature_name', 'is_enabled', 'limit_value']


class PlanSerializer(serializers.ModelSerializer):
    """Serializer for Plan model."""

    plan_features = PlanFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'display_name', 'description',
            'price_monthly', 'price_yearly', 'max_students',
            'max_teachers', 'max_storage_gb', 'ai_credits_monthly',
            'features', 'plan_features', 'sort_order',
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model."""

    plan_name = serializers.CharField(source='plan.display_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)
    days_until_expiry = serializers.ReadOnlyField()
    is_active_or_trial = serializers.ReadOnlyField()
    is_in_grace_period = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'school', 'school_name', 'plan', 'plan_name',
            'status', 'billing_cycle', 'trial_start', 'trial_end',
            'current_period_start', 'current_period_end',
            'cancelled_at', 'cancel_reason', 'auto_renew',
            'days_until_expiry', 'is_active_or_trial', 'is_in_grace_period',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'school', 'status', 'trial_start', 'trial_end',
            'current_period_start', 'current_period_end',
            'cancelled_at', 'created_at', 'updated_at',
        ]


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionHistory model."""

    from_plan_name = serializers.CharField(source='from_plan.display_name', read_only=True, default=None)
    to_plan_name = serializers.CharField(source='to_plan.display_name', read_only=True, default=None)

    class Meta:
        model = SubscriptionHistory
        fields = [
            'id', 'action', 'from_plan', 'from_plan_name',
            'to_plan', 'to_plan_name', 'metadata', 'created_at',
        ]


class UpgradePlanSerializer(serializers.Serializer):
    """Serializer for plan upgrade/downgrade."""

    plan_id = serializers.UUIDField(required=True)
    billing_cycle = serializers.ChoiceField(
        choices=Subscription.BillingCycle.choices,
        required=False,
    )


class CancelSubscriptionSerializer(serializers.Serializer):
    """Serializer for subscription cancellation."""

    reason = serializers.CharField(required=False, allow_blank=True, default='')


class AICreditSerializer(serializers.ModelSerializer):
    """Serializer for AICredit model."""

    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = AICredit
        fields = [
            'id', 'school_name', 'balance', 'monthly_allocation',
            'last_reset_date', 'updated_at',
        ]
        read_only_fields = fields


class AddOnSerializer(serializers.ModelSerializer):
    """Serializer for AddOn model."""

    class Meta:
        model = AddOn
        fields = [
            'id', 'name', 'description', 'addon_type',
            'price', 'value', 'is_active',
        ]


class SchoolAddOnSerializer(serializers.ModelSerializer):
    """Serializer for SchoolAddOn model."""

    addon_name = serializers.CharField(source='addon.name', read_only=True)
    addon_type = serializers.CharField(source='addon.addon_type', read_only=True)
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = SchoolAddOn
        fields = [
            'id', 'addon', 'addon_name', 'addon_type',
            'quantity', 'purchased_at', 'expires_at',
            'is_active', 'is_expired',
        ]
        read_only_fields = ['id', 'purchased_at']
