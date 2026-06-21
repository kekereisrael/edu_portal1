"""
Models for the subscriptions app - Plans, subscriptions, and feature gating.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """Subscription plan definition."""

    class PlanName(models.TextChoices):
        FREE = 'free', 'Free'
        BASIC = 'basic', 'Basic'
        STANDARD = 'standard', 'Standard'
        PREMIUM = 'premium', 'Premium'
        ENTERPRISE = 'enterprise', 'Enterprise'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=PlanName.choices, unique=True, db_index=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_students = models.IntegerField(default=50, help_text='-1 for unlimited')
    max_teachers = models.IntegerField(default=5, help_text='-1 for unlimited')
    max_storage_gb = models.IntegerField(default=1)
    ai_credits_monthly = models.IntegerField(default=0)
    features = models.JSONField(
        default=dict,
        help_text='Feature flags: {"basic_exams": true, "materials": false, ...}',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'plan'
        verbose_name_plural = 'plans'
        ordering = ['sort_order']

    def __str__(self):
        return self.display_name

    def has_feature(self, feature_key):
        """Check if this plan includes a specific feature."""
        return self.features.get(feature_key, False)

    def get_limit(self, limit_key):
        """Get a numeric limit for this plan."""
        limits = {
            'max_students': self.max_students,
            'max_teachers': self.max_teachers,
            'max_storage_gb': self.max_storage_gb,
            'ai_credits_monthly': self.ai_credits_monthly,
        }
        return limits.get(limit_key, 0)


class PlanFeature(models.Model):
    """Individual feature definition for a plan."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='plan_features', db_index=True)
    feature_key = models.CharField(max_length=50, db_index=True)
    feature_name = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=False)
    limit_value = models.IntegerField(null=True, blank=True, help_text='Numeric limit if applicable')

    class Meta:
        verbose_name = 'plan feature'
        verbose_name_plural = 'plan features'
        unique_together = ['plan', 'feature_key']

    def __str__(self):
        status = 'Enabled' if self.is_enabled else 'Disabled'
        return f'{self.plan.display_name} - {self.feature_name} ({status})'


class Subscription(models.Model):
    """School subscription to a plan."""

    class Status(models.TextChoices):
        TRIAL = 'trial', 'Trial'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past Due'
        CANCELLED = 'cancelled', 'Cancelled'
        EXPIRED = 'expired', 'Expired'

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        'schools.School', on_delete=models.CASCADE, related_name='subscription', db_index=True
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions', db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRIAL, db_index=True
    )
    billing_cycle = models.CharField(
        max_length=10, choices=BillingCycle.choices, default=BillingCycle.MONTHLY
    )
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True, db_index=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True, null=True)
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'subscription'
        verbose_name_plural = 'subscriptions'

    def __str__(self):
        return f'{self.school.name} - {self.plan.display_name} ({self.status})'

    @property
    def is_active_or_trial(self):
        """Check if subscription allows access."""
        return self.status in [self.Status.TRIAL, self.Status.ACTIVE]

    @property
    def is_in_grace_period(self):
        """Check if subscription is in the 7-day grace period after expiry."""
        if self.status != self.Status.PAST_DUE:
            return False
        if not self.current_period_end:
            return False
        grace_end = self.current_period_end + timezone.timedelta(days=7)
        return timezone.now() <= grace_end

    @property
    def days_until_expiry(self):
        """Days until current period ends."""
        if self.status == self.Status.TRIAL and self.trial_end:
            delta = self.trial_end - timezone.now()
            return max(0, delta.days)
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0

    def has_feature(self, feature_key):
        """Check if the subscription's plan includes a feature."""
        return self.plan.has_feature(feature_key)

    def activate(self, period_start=None, period_end=None):
        """Activate the subscription after payment."""
        self.status = self.Status.ACTIVE
        self.current_period_start = period_start or timezone.now()
        if not period_end:
            if self.billing_cycle == self.BillingCycle.MONTHLY:
                self.current_period_end = self.current_period_start + timezone.timedelta(days=30)
            else:
                self.current_period_end = self.current_period_start + timezone.timedelta(days=365)
        else:
            self.current_period_end = period_end
        self.save()

        # Log history
        SubscriptionHistory.objects.create(
            subscription=self,
            action=SubscriptionHistory.Action.RENEWED if self.current_period_start else SubscriptionHistory.Action.CREATED,
            to_plan=self.plan,
        )

    def cancel(self, reason=''):
        """Cancel the subscription."""
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancel_reason = reason
        self.auto_renew = False
        self.save()

        SubscriptionHistory.objects.create(
            subscription=self,
            action=SubscriptionHistory.Action.CANCELLED,
            from_plan=self.plan,
            metadata={'reason': reason},
        )

    def expire(self):
        """Mark subscription as expired."""
        self.status = self.Status.EXPIRED
        self.save()

        SubscriptionHistory.objects.create(
            subscription=self,
            action=SubscriptionHistory.Action.EXPIRED,
            from_plan=self.plan,
        )

    def upgrade(self, new_plan):
        """Upgrade to a higher plan."""
        old_plan = self.plan
        self.plan = new_plan
        self.save()

        SubscriptionHistory.objects.create(
            subscription=self,
            action=SubscriptionHistory.Action.UPGRADED,
            from_plan=old_plan,
            to_plan=new_plan,
        )

    def downgrade(self, new_plan):
        """Downgrade to a lower plan."""
        old_plan = self.plan
        self.plan = new_plan
        self.save()

        SubscriptionHistory.objects.create(
            subscription=self,
            action=SubscriptionHistory.Action.DOWNGRADED,
            from_plan=old_plan,
            to_plan=new_plan,
        )


class SubscriptionHistory(models.Model):
    """Audit trail for subscription changes."""

    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPGRADED = 'upgraded', 'Upgraded'
        DOWNGRADED = 'downgraded', 'Downgraded'
        RENEWED = 'renewed', 'Renewed'
        CANCELLED = 'cancelled', 'Cancelled'
        EXPIRED = 'expired', 'Expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='history', db_index=True
    )
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    from_plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    to_plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'subscription history'
        verbose_name_plural = 'subscription histories'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subscription.school.name} - {self.action} at {self.created_at}'


class AICredit(models.Model):
    """AI credit balance for a school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        'schools.School', on_delete=models.CASCADE, related_name='ai_credits', db_index=True
    )
    balance = models.IntegerField(default=0)
    monthly_allocation = models.IntegerField(default=0)
    last_reset_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI credit'
        verbose_name_plural = 'AI credits'

    def __str__(self):
        return f'{self.school.name} - {self.balance} credits'

    def consume(self, amount=1):
        """Consume AI credits. Returns True if successful."""
        if self.balance >= amount:
            self.balance -= amount
            self.save(update_fields=['balance', 'updated_at'])
            return True
        return False

    def reset_monthly(self):
        """Reset credits to monthly allocation."""
        self.balance = self.monthly_allocation
        self.last_reset_date = timezone.now().date()
        self.save(update_fields=['balance', 'last_reset_date', 'updated_at'])


class AddOn(models.Model):
    """Purchasable add-ons for schools."""

    class AddOnType(models.TextChoices):
        AI_CREDITS = 'ai_credits', 'AI Credits'
        STORAGE = 'storage', 'Additional Storage'
        SMS = 'sms', 'SMS Credits'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    addon_type = models.CharField(max_length=20, choices=AddOnType.choices, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    value = models.IntegerField(help_text='Number of credits/GB/SMS included')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'add-on'
        verbose_name_plural = 'add-ons'
        ordering = ['addon_type', 'price']

    def __str__(self):
        return f'{self.name} - NGN {self.price}'


class SchoolAddOn(models.Model):
    """Active add-ons purchased by a school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='addons', db_index=True
    )
    addon = models.ForeignKey(AddOn, on_delete=models.PROTECT, related_name='purchases')
    quantity = models.IntegerField(default=1)
    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'school add-on'
        verbose_name_plural = 'school add-ons'
        ordering = ['-purchased_at']

    def __str__(self):
        return f'{self.school.name} - {self.addon.name}'

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
