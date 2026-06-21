"""
Serializers for the payments app.
"""

from rest_framework import serializers

from .models import Payment, Invoice, Refund, Coupon


class PaymentSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)

    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'user_email', 'amount', 'currency',
            'payment_gateway', 'gateway_reference', 'status',
            'payment_type', 'description', 'paid_at', 'created_at',
        ]
        read_only_fields = fields


class InitializePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    gateway = serializers.ChoiceField(choices=Payment.Gateway.choices)
    payment_type = serializers.ChoiceField(choices=Payment.PaymentType.choices)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    coupon_code = serializers.CharField(required=False, allow_blank=True, default='')


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'amount', 'tax_amount',
            'total_amount', 'status', 'due_date', 'paid_at',
            'line_items', 'pdf_url', 'created_at',
        ]
        read_only_fields = fields


class RefundSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField()


class ValidateCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=30)
