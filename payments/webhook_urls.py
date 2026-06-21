"""
Webhook URL configuration for the payments app.
"""

from django.urls import path

from . import webhook_views

urlpatterns = [
    path('paystack/', webhook_views.PaystackWebhookView.as_view(), name='paystack_webhook'),
    path('flutterwave/', webhook_views.FlutterwaveWebhookView.as_view(), name='flutterwave_webhook'),
]
