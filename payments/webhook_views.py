"""
Webhook views for payment gateway callbacks.
"""

import hashlib
import hmac
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WebhookEvent


class PaystackWebhookView(APIView):
    """Handle Paystack webhook events."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Verify signature
        signature = request.headers.get('X-Paystack-Signature', '')
        payload = request.body

        if not self._verify_signature(payload, signature):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        event_type = data.get('event', '')
        event_id = data.get('data', {}).get('id', str(data.get('data', {}).get('reference', '')))

        # Idempotency check
        if WebhookEvent.objects.filter(event_id=str(event_id), gateway='paystack').exists():
            return Response(status=status.HTTP_200_OK)

        # Store event
        WebhookEvent.objects.create(
            gateway='paystack',
            event_type=event_type,
            event_id=str(event_id),
            payload=data,
        )

        # Process asynchronously
        from .tasks import process_paystack_webhook
        process_paystack_webhook.delay(str(event_id))

        return Response(status=status.HTTP_200_OK)

    def _verify_signature(self, payload, signature):
        secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
        computed = hmac.new(secret, payload, hashlib.sha512).hexdigest()
        return hmac.compare_digest(computed, signature)


class FlutterwaveWebhookView(APIView):
    """Handle Flutterwave webhook events."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Verify hash
        secret_hash = settings.FLUTTERWAVE_SECRET_KEY
        signature = request.headers.get('verif-hash', '')

        if signature != secret_hash:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        event_type = data.get('event', '')
        event_id = str(data.get('data', {}).get('id', ''))

        # Idempotency check
        if WebhookEvent.objects.filter(event_id=event_id, gateway='flutterwave').exists():
            return Response(status=status.HTTP_200_OK)

        # Store event
        WebhookEvent.objects.create(
            gateway='flutterwave',
            event_type=event_type,
            event_id=event_id,
            payload=data,
        )

        # Process asynchronously
        from .tasks import process_flutterwave_webhook
        process_flutterwave_webhook.delay(event_id)

        return Response(status=status.HTTP_200_OK)
