"""
Views for the subscriptions app.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from schools.permissions import HasSchoolContext, IsSchoolAdmin, IsPlatformAdmin
from .models import (
    Plan, Subscription, SubscriptionHistory, AICredit, AddOn, SchoolAddOn,
)
from .serializers import (
    PlanSerializer, SubscriptionSerializer, SubscriptionHistorySerializer,
    UpgradePlanSerializer, CancelSubscriptionSerializer,
    AICreditSerializer, AddOnSerializer, SchoolAddOnSerializer,
)


class PlanListView(generics.ListAPIView):
    """List all available subscription plans."""

    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Plan.objects.filter(is_active=True)


class PlanDetailView(generics.RetrieveAPIView):
    """Get details of a specific plan."""

    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Plan.objects.filter(is_active=True)


class CurrentSubscriptionView(generics.RetrieveAPIView):
    """Get the current school's subscription details."""

    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_object(self):
        try:
            return self.request.school.subscription
        except Subscription.DoesNotExist:
            return None

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance is None:
            return Response(
                {'detail': 'No subscription found. Please subscribe to a plan.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class SubscriptionHistoryView(generics.ListAPIView):
    """List subscription history for the current school."""

    serializer_class = SubscriptionHistorySerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        try:
            subscription = self.request.school.subscription
            return subscription.history.all()
        except Subscription.DoesNotExist:
            return SubscriptionHistory.objects.none()


class UpgradePlanView(APIView):
    """Upgrade or change the subscription plan."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = UpgradePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_id = serializer.validated_data['plan_id']
        new_plan = get_object_or_404(Plan, id=plan_id, is_active=True)

        try:
            subscription = request.school.subscription
        except Subscription.DoesNotExist:
            return Response(
                {'detail': 'No subscription found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if subscription.plan == new_plan:
            return Response(
                {'detail': 'Already on this plan.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine if upgrade or downgrade
        if new_plan.sort_order > subscription.plan.sort_order:
            subscription.upgrade(new_plan)
            message = f'Successfully upgraded to {new_plan.display_name}.'
        else:
            subscription.downgrade(new_plan)
            message = f'Successfully downgraded to {new_plan.display_name}. Changes take effect at next billing cycle.'

        # Update billing cycle if provided
        billing_cycle = serializer.validated_data.get('billing_cycle')
        if billing_cycle:
            subscription.billing_cycle = billing_cycle
            subscription.save(update_fields=['billing_cycle'])

        # Update AI credits allocation
        ai_credits, _ = AICredit.objects.get_or_create(school=request.school)
        ai_credits.monthly_allocation = new_plan.ai_credits_monthly
        ai_credits.save(update_fields=['monthly_allocation', 'updated_at'])

        return Response(
            {
                'message': message,
                'subscription': SubscriptionSerializer(subscription).data,
            },
            status=status.HTTP_200_OK,
        )


class CancelSubscriptionView(APIView):
    """Cancel the current subscription."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            subscription = request.school.subscription
        except Subscription.DoesNotExist:
            return Response(
                {'detail': 'No subscription found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if subscription.status == Subscription.Status.CANCELLED:
            return Response(
                {'detail': 'Subscription is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = serializer.validated_data.get('reason', '')
        subscription.cancel(reason=reason)

        return Response(
            {
                'message': 'Subscription cancelled. Access continues until end of current billing period.',
                'subscription': SubscriptionSerializer(subscription).data,
            },
            status=status.HTTP_200_OK,
        )


class AICreditView(generics.RetrieveAPIView):
    """Get AI credit balance for the current school."""

    serializer_class = AICreditSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_object(self):
        credits, _ = AICredit.objects.get_or_create(
            school=self.request.school,
            defaults={'monthly_allocation': self.request.school.subscription.plan.ai_credits_monthly}
            if hasattr(self.request.school, 'subscription')
            else {'monthly_allocation': 0},
        )
        return credits


class AddOnListView(generics.ListAPIView):
    """List all available add-ons."""

    serializer_class = AddOnSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = AddOn.objects.filter(is_active=True)


class SchoolAddOnListView(generics.ListAPIView):
    """List add-ons purchased by the current school."""

    serializer_class = SchoolAddOnSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return SchoolAddOn.objects.filter(
            school=self.request.school, is_active=True
        ).select_related('addon')


# ============ Platform Admin Views ============

class AllSubscriptionsView(generics.ListAPIView):
    """List all subscriptions (platform admin only)."""

    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]
    queryset = Subscription.objects.all().select_related('school', 'plan')
    filterset_fields = ['status', 'plan__name', 'billing_cycle']
    search_fields = ['school__name', 'school__email']
