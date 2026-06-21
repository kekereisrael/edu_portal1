"""
URL configuration for the subscriptions app.
"""

from django.urls import path

from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Plans (public)
    path('plans/', views.PlanListView.as_view(), name='plan_list'),
    path('plans/<uuid:pk>/', views.PlanDetailView.as_view(), name='plan_detail'),

    # Current subscription
    path('current/', views.CurrentSubscriptionView.as_view(), name='current_subscription'),
    path('history/', views.SubscriptionHistoryView.as_view(), name='subscription_history'),

    # Plan changes
    path('upgrade/', views.UpgradePlanView.as_view(), name='upgrade_plan'),
    path('cancel/', views.CancelSubscriptionView.as_view(), name='cancel_subscription'),

    # AI Credits
    path('ai-credits/', views.AICreditView.as_view(), name='ai_credits'),

    # Add-ons
    path('addons/', views.AddOnListView.as_view(), name='addon_list'),
    path('addons/my/', views.SchoolAddOnListView.as_view(), name='school_addon_list'),

    # Platform admin
    path('admin/all/', views.AllSubscriptionsView.as_view(), name='all_subscriptions'),
]
