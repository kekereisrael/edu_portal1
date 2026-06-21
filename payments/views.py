"""
Views for the payments app.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasSchoolContext, IsSchoolAdmin

from .models import Payment, Invoice, Refund, Coupon
from .serializers import (
    PaymentSerializer, InitializePaymentSerializer,
    InvoiceSerializer, RefundSerializer, ValidateCouponSerializer,
)


class InitializePaymentView(APIView):
    """Initialize a payment with the gateway."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = InitializePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create payment record
        payment = Payment.objects.create(
            school=request.school,
            user=request.user,
            amount=serializer.validated_data['amount'],
            payment_gateway=serializer.validated_data['gateway'],
            payment_type=serializer.validated_data['payment_type'],
            description=serializer.validated_data.get('description', ''),
        )

        # TODO: Call payment gateway API to initialize transaction
        # For now, return the payment record
        return Response(
            {
                'payment': PaymentSerializer(payment).data,
                'message': 'Payment initialized. Redirect to gateway.',
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyPaymentView(APIView):
    """Verify a payment with the gateway."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get(self, request, reference):
        payment = get_object_or_404(
            Payment, gateway_reference=reference, school=request.school
        )
        # TODO: Verify with gateway API
        return Response(PaymentSerializer(payment).data)


class PaymentHistoryView(generics.ListAPIView):
    """List payment history for the school."""

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]
    filterset_fields = ['status', 'payment_type', 'payment_gateway']
    ordering_fields = ['amount', 'created_at']

    def get_queryset(self):
        return Payment.objects.filter(
            school=self.request.school
        ).select_related('user')


class InvoiceListView(generics.ListAPIView):
    """List invoices for the school."""

    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]
    filterset_fields = ['status']

    def get_queryset(self):
        return Invoice.objects.filter(school=self.request.school)


class InvoiceDetailView(generics.RetrieveAPIView):
    """Get invoice detail."""

    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return Invoice.objects.filter(school=self.request.school)


class RequestRefundView(APIView):
    """Request a refund for a payment."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = get_object_or_404(
            Payment,
            id=serializer.validated_data['payment_id'],
            school=request.school,
            status=Payment.Status.SUCCESSFUL,
        )

        refund = Refund.objects.create(
            payment=payment,
            amount=serializer.validated_data['amount'],
            reason=serializer.validated_data['reason'],
        )

        return Response(
            {'message': 'Refund request submitted.', 'refund_id': str(refund.id)},
            status=status.HTTP_201_CREATED,
        )


class ValidateCouponView(APIView):
    """Validate a coupon code."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request):
        serializer = ValidateCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code']
        try:
            coupon = Coupon.objects.get(code=code.upper())
        except Coupon.DoesNotExist:
            return Response(
                {'detail': 'Invalid coupon code.', 'valid': False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not coupon.is_valid:
            return Response(
                {'detail': 'Coupon has expired or reached maximum redemptions.', 'valid': False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already used by this school
        from .models import CouponRedemption
        if CouponRedemption.objects.filter(coupon=coupon, school=request.school).exists():
            return Response(
                {'detail': 'Coupon already used by this school.', 'valid': False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'valid': True,
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': str(coupon.discount_value),
        })
