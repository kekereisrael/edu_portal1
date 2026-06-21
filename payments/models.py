"""
Models for the payments app.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel, SchoolScopedModel


class Payment(SchoolScopedModel):
    """Payment transaction record."""

    class Gateway(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'
        FLUTTERWAVE = 'flutterwave', 'Flutterwave'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SUCCESSFUL = 'successful', 'Successful'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    class PaymentType(models.TextChoices):
        SUBSCRIPTION = 'subscription', 'Subscription'
        ADDON = 'addon', 'Add-on Purchase'
        AI_CREDITS = 'ai_credits', 'AI Credits'
        STORAGE = 'storage', 'Storage Add-on'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments',
        db_index=True,
        help_text='User who initiated the payment',
    )
    subscription = models.ForeignKey(
        'subscriptions.Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    payment_gateway = models.CharField(max_length=20, choices=Gateway.choices)
    gateway_reference = models.CharField(
        max_length=100, unique=True, null=True, blank=True, db_index=True
    )
    gateway_response = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    description = models.TextField(blank=True, null=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'payment'
        verbose_name_plural = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'status', 'created_at'], name='idx_payment_school_status'),
            models.Index(fields=['user', 'status'], name='idx_payment_user_status'),
        ]

    def __str__(self):
        return f'{self.school.name} - {self.amount} {self.currency} ({self.status})'


class Invoice(SchoolScopedModel):
    """Invoice for a payment."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'

    payment = models.OneToOneField(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice'
    )
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    line_items = models.JSONField(
        default=list,
        help_text='[{"description": "Basic Plan - Monthly", "amount": 15000}]',
    )
    pdf_url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = 'invoice'
        verbose_name_plural = 'invoices'
        ordering = ['-created_at']

    def __str__(self):
        return f'Invoice {self.invoice_number} - {self.total_amount} {self.status}'


class Refund(BaseModel):
    """Refund tracking."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='refunds', db_index=True
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    gateway_reference = models.CharField(max_length=100, null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds',
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'refund'
        verbose_name_plural = 'refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f'Refund {self.amount} for {self.payment}'


class Coupon(BaseModel):
    """Discount codes for subscriptions."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED_AMOUNT = 'fixed_amount', 'Fixed Amount'

    code = models.CharField(max_length=30, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_redemptions = models.IntegerField(
        null=True, blank=True, help_text='Null = unlimited'
    )
    current_redemptions = models.IntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    applicable_plans = models.ManyToManyField(
        'subscriptions.Plan', blank=True, related_name='coupons'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'coupon'
        verbose_name_plural = 'coupons'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} - {self.discount_value}{"%" if self.discount_type == "percentage" else " NGN"}'

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.max_redemptions and self.current_redemptions >= self.max_redemptions:
            return False
        return True

    def calculate_discount(self, amount):
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return amount * (self.discount_value / 100)
        return min(self.discount_value, amount)


class CouponRedemption(BaseModel):
    """Track coupon usage."""

    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name='redemptions', db_index=True
    )
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='coupon_redemptions'
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupon_redemptions'
    )
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'coupon redemption'
        verbose_name_plural = 'coupon redemptions'
        unique_together = ['coupon', 'school']

    def __str__(self):
        return f'{self.school.name} used {self.coupon.code}'


class PaymentRetryLog(BaseModel):
    """Track retry attempts for failed payments."""

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='retry_logs', db_index=True
    )
    attempt_number = models.IntegerField()
    gateway_response = models.JSONField(default=dict)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'payment retry log'
        verbose_name_plural = 'payment retry logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'Retry #{self.attempt_number} for {self.payment}'


class WebhookEvent(BaseModel):
    """Record of webhook events from payment gateways."""

    class Gateway(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'
        FLUTTERWAVE = 'flutterwave', 'Flutterwave'

    gateway = models.CharField(max_length=20, choices=Gateway.choices, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    event_id = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text='Unique event ID from the gateway for idempotency',
    )
    payload = models.JSONField()
    is_processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'webhook event'
        verbose_name_plural = 'webhook events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.gateway} - {self.event_type} ({self.event_id})'
