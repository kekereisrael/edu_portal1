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


class PlanChangeRequest(models.Model):
    """Pending upgrade/downgrade requests for handling proration and scheduled changes."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='change_requests', db_index=True
    )
    from_plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name='change_requests_from'
    )
    to_plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name='change_requests_to'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    change_type = models.CharField(
        max_length=10,
        choices=[('upgrade', 'Upgrade'), ('downgrade', 'Downgrade')],
    )
    scheduled_date = models.DateTimeField(
        help_text='When the change should take effect'
    )
    proration_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Amount to credit/charge for proration'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'plan change request'
        verbose_name_plural = 'plan change requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['subscription', 'status'], name='idx_planchange_sub_status'
            ),
        ]

    def __str__(self):
        return f'{self.subscription.school.name}: {self.from_plan.name} -> {self.to_plan.name} ({self.status})'

    def complete(self):
        """Mark the change request as completed and apply the plan change."""
        if self.change_type == 'upgrade':
            self.subscription.upgrade(self.to_plan)
        else:
            self.subscription.downgrade(self.to_plan)
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def cancel(self):
        """Cancel the pending change request."""
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancelled_at'])


class UsageRecord(models.Model):
    """Track feature usage against plan limits for enforcement and analytics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='usage_records', db_index=True
    )
    feature_key = models.CharField(
        max_length=50, db_index=True,
        help_text='Feature identifier, e.g. "exams_created", "materials_uploaded", "ai_requests"'
    )
    usage_count = models.IntegerField(default=0)
    usage_limit = models.IntegerField(
        default=-1, help_text='-1 for unlimited'
    )
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'usage record'
        verbose_name_plural = 'usage records'
        unique_together = ['school', 'feature_key', 'period_start']
        ordering = ['-period_start']
        indexes = [
            models.Index(
                fields=['school', 'feature_key', 'period_start'],
                name='idx_usage_school_feature_period',
            ),
        ]

    def __str__(self):
        return f'{self.school.name} - {self.feature_key}: {self.usage_count}/{self.usage_limit}'

    @property
    def is_within_limit(self):
        """Check if usage is within the allowed limit."""
        if self.usage_limit == -1:
            return True  # Unlimited
        return self.usage_count < self.usage_limit

    @property
    def usage_percentage(self):
        """Get usage as a percentage of the limit."""
        if self.usage_limit == -1:
            return 0
        if self.usage_limit == 0:
            return 100
        return min(100, (self.usage_count / self.usage_limit) * 100)

    def increment(self, amount=1):
        """Increment usage count. Returns True if within limit."""
        if not self.is_within_limit:
            return False
        self.usage_count += amount
        self.save(update_fields=['usage_count', 'updated_at'])
        return True


class TrialExtension(models.Model):
    """Track trial extensions granted to schools."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='trial_extensions', db_index=True
    )
    extended_days = models.IntegerField(
        help_text='Number of days the trial was extended'
    )
    reason = models.TextField(
        help_text='Reason for granting the extension'
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_trial_extensions',
    )
    original_trial_end = models.DateTimeField(
        help_text='Trial end date before extension'
    )
    new_trial_end = models.DateTimeField(
        help_text='Trial end date after extension'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'trial extension'
        verbose_name_plural = 'trial extensions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subscription.school.name} - +{self.extended_days} days'

    def save(self, *args, **kwargs):
        if not self.original_trial_end:
            self.original_trial_end = self.subscription.trial_end
        if not self.new_trial_end:
            self.new_trial_end = self.original_trial_end + timezone.timedelta(
                days=self.extended_days
            )
        super().save(*args, **kwargs)
        # Update the subscription trial end date
        self.subscription.trial_end = self.new_trial_end
        self.subscription.save(update_fields=['trial_end'])


class Referral(models.Model):
    """Track school referrals for the referral program."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer_school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='referrals_made', db_index=True,
    )
    referred_school = models.ForeignKey(
        'schools.School', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referred_by',
    )
    referral_code = models.CharField(
        max_length=20, unique=True, db_index=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Referral code expiry date'
    )

    class Meta:
        verbose_name = 'referral'
        verbose_name_plural = 'referrals'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.referrer_school.name} -> {self.referral_code} ({self.status})'

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def complete(self, referred_school):
        """Mark referral as completed when referred school subscribes."""
        self.referred_school = referred_school
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['referred_school', 'status', 'completed_at'])


class ReferralReward(models.Model):
    """Rewards earned from successful referrals."""

    class RewardType(models.TextChoices):
        CREDIT = 'credit', 'Account Credit'
        DISCOUNT = 'discount', 'Subscription Discount'
        EXTENSION = 'extension', 'Subscription Extension'
        AI_CREDITS = 'ai_credits', 'AI Credits'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.OneToOneField(
        Referral, on_delete=models.CASCADE, related_name='reward'
    )
    reward_type = models.CharField(
        max_length=20, choices=RewardType.choices
    )
    reward_value = models.IntegerField(
        help_text='Value depends on type: credit amount in NGN, discount %, days extension, or AI credits'
    )
    is_claimed = models.BooleanField(default=False)
    claimed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Reward expiry date'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'referral reward'
        verbose_name_plural = 'referral rewards'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.referral.referrer_school.name} - {self.reward_type}: {self.reward_value}'

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def is_claimable(self):
        return not self.is_claimed and not self.is_expired

    def claim(self):
        """Claim the reward."""
        if not self.is_claimable:
            raise ValueError('Reward is not claimable (already claimed or expired).')
        self.is_claimed = True
        self.claimed_at = timezone.now()
        self.save(update_fields=['is_claimed', 'claimed_at'])
        # Apply the reward based on type
        self._apply_reward()

    def _apply_reward(self):
        """Apply the reward to the referrer school."""
        school = self.referral.referrer_school
        if self.reward_type == self.RewardType.AI_CREDITS:
            try:
                ai_credit = school.ai_credits
                ai_credit.balance += self.reward_value
                ai_credit.save(update_fields=['balance', 'updated_at'])
            except Exception:
                pass
        elif self.reward_type == self.RewardType.EXTENSION:
            try:
                subscription = school.subscription
                if subscription.current_period_end:
                    subscription.current_period_end += timezone.timedelta(
                        days=self.reward_value
                    )
                    subscription.save(update_fields=['current_period_end'])
            except Exception:
                pass
