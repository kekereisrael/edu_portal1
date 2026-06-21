"""
URL configuration for the payments app.
"""

from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('initialize/', views.InitializePaymentView.as_view(), name='initialize'),
    path('verify/<str:reference>/', views.VerifyPaymentView.as_view(), name='verify'),
    path('history/', views.PaymentHistoryView.as_view(), name='history'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<uuid:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('refund/', views.RequestRefundView.as_view(), name='request_refund'),
    path('coupons/validate/', views.ValidateCouponView.as_view(), name='validate_coupon'),
]
