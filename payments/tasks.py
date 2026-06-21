"""
Celery tasks for the payments app.
"""

from celery import shared_task


@shared_task(queue='payments')
def process_paystack_webhook(event_id):
    """Process a Paystack webhook event."""
    from .models import WebhookEvent, Payment
    from django.utils import timezone

    try:
        event = WebhookEvent.objects.get(event_id=event_id, gateway='paystack')
        data = event.payload.get('data', {})
        event_type = event.event_type

        if event_type == 'charge.success':
            reference = data.get('reference')
            if reference:
                try:
                    payment = Payment.objects.get(gateway_reference=reference)
                    payment.status = Payment.Status.SUCCESSFUL
                    payment.paid_at = timezone.now()
                    payment.gateway_response = data
                    payment.save()

                    # Activate subscription if payment is for subscription
                    if payment.subscription:
                        payment.subscription.activate()
                except Payment.DoesNotExist:
                    pass

        event.is_processed = True
        event.processed_at = timezone.now()
        event.save()

    except WebhookEvent.DoesNotExist:
        pass
    except Exception as e:
        event.error_message = str(e)
        event.save()


@shared_task(queue='payments')
def process_flutterwave_webhook(event_id):
    """Process a Flutterwave webhook event."""
    from .models import WebhookEvent, Payment
    from django.utils import timezone

    try:
        event = WebhookEvent.objects.get(event_id=event_id, gateway='flutterwave')
        data = event.payload.get('data', {})
        event_type = event.event_type

        if event_type == 'charge.completed':
            tx_ref = data.get('tx_ref')
            if tx_ref:
                try:
                    payment = Payment.objects.get(gateway_reference=tx_ref)
                    if data.get('status') == 'successful':
                        payment.status = Payment.Status.SUCCESSFUL
                        payment.paid_at = timezone.now()
                    else:
                        payment.status = Payment.Status.FAILED
                    payment.gateway_response = data
                    payment.save()

                    if payment.status == Payment.Status.SUCCESSFUL and payment.subscription:
                        payment.subscription.activate()
                except Payment.DoesNotExist:
                    pass

        event.is_processed = True
        event.processed_at = timezone.now()
        event.save()

    except WebhookEvent.DoesNotExist:
        pass
    except Exception as e:
        event.error_message = str(e)
        event.save()
