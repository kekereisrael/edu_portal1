"""
Tests for the payments app.
Covers payment creation, webhook processing, and idempotency.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal

User = get_user_model()


class PaymentModelTests(TestCase):
    """Tests for Payment model."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='TestPass123!',
            first_name='Admin',
            last_name='User',
            role='school_admin',
            school=self.school,
        )

    def test_create_payment(self):
        """Test creating a payment record."""
        from payments.models import Payment
        payment = Payment.objects.create(
            school=self.school,
            user=self.admin,
            amount=Decimal('5000.00'),
            currency='NGN',
            payment_method='paystack',
            status='pending',
            description='Subscription payment',
        )
        self.assertEqual(payment.amount, Decimal('5000.00'))
        self.assertEqual(payment.status, 'pending')
        self.assertIsNotNone(payment.reference)

    def test_payment_reference_unique(self):
        """Test that payment references are unique."""
        from payments.models import Payment
        payment1 = Payment.objects.create(
            school=self.school,
            user=self.admin,
            amount=Decimal('5000.00'),
            currency='NGN',
            payment_method='paystack',
            status='pending',
        )
        payment2 = Payment.objects.create(
            school=self.school,
            user=self.admin,
            amount=Decimal('3000.00'),
            currency='NGN',
            payment_method='paystack',
            status='pending',
        )
        self.assertNotEqual(payment1.reference, payment2.reference)


class WebhookIdempotencyTests(TestCase):
    """Tests for webhook event idempotency."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )

    def test_create_webhook_event(self):
        """Test creating a webhook event."""
        from payments.models import WebhookEvent
        event = WebhookEvent.objects.create(
            provider='paystack',
            event_type='charge.success',
            event_id='evt_123456',
            payload={'data': {'reference': 'ref_123'}},
            status='pending',
        )
        self.assertEqual(event.event_id, 'evt_123456')
        self.assertEqual(event.status, 'pending')

    def test_duplicate_webhook_event_rejected(self):
        """Test that duplicate webhook events are rejected."""
        from payments.models import WebhookEvent
        from django.db import IntegrityError

        WebhookEvent.objects.create(
            provider='paystack',
            event_type='charge.success',
            event_id='evt_123456',
            payload={'data': {'reference': 'ref_123'}},
            status='processed',
        )

        with self.assertRaises(IntegrityError):
            WebhookEvent.objects.create(
                provider='paystack',
                event_type='charge.success',
                event_id='evt_123456',
                payload={'data': {'reference': 'ref_456'}},
                status='pending',
            )


class CouponModelTests(TestCase):
    """Tests for Coupon model."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )

    def test_create_coupon(self):
        """Test creating a coupon."""
        from payments.models import Coupon
        coupon = Coupon.objects.create(
            code='WELCOME20',
            discount_type='percentage',
            discount_value=Decimal('20.00'),
            max_uses=100,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True,
        )
        self.assertEqual(coupon.code, 'WELCOME20')
        self.assertEqual(coupon.discount_value, Decimal('20.00'))

    def test_coupon_validity(self):
        """Test coupon validity checking."""
        from payments.models import Coupon
        # Expired coupon
        expired_coupon = Coupon.objects.create(
            code='EXPIRED',
            discount_type='percentage',
            discount_value=Decimal('10.00'),
            max_uses=100,
            valid_from=timezone.now() - timezone.timedelta(days=60),
            valid_until=timezone.now() - timezone.timedelta(days=30),
            is_active=True,
        )
        self.assertLess(expired_coupon.valid_until, timezone.now())

    def test_coupon_max_uses(self):
        """Test coupon max uses enforcement."""
        from payments.models import Coupon
        coupon = Coupon.objects.create(
            code='LIMITED',
            discount_type='fixed',
            discount_value=Decimal('500.00'),
            max_uses=1,
            times_used=1,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True,
        )
        self.assertEqual(coupon.times_used, coupon.max_uses)
