"""
Subscription middleware for feature gating.
"""

from django.http import JsonResponse

from .models import Subscription


class SubscriptionMiddleware:
    """
    Middleware that checks subscription status and gates features.
    
    Runs after SchoolContextMiddleware. If a school's subscription is
    expired or missing, restricts access to billing-related pages only.
    """

    EXEMPT_URL_PREFIXES = [
        '/admin/',
        '/api/v1/auth/',
        '/api/v1/schools/create/',
        '/api/v1/subscriptions/plans/',
        '/api/v1/subscriptions/current/',
        '/api/v1/payments/',
        '/webhooks/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for exempt URLs
        if self._is_exempt(request):
            return self.get_response(request)

        # Skip for unauthenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        # Platform admins bypass subscription checks
        if request.user.is_platform_admin:
            return self.get_response(request)

        # Skip if no school context (handled by SchoolContextMiddleware)
        if not hasattr(request, 'school') or request.school is None:
            return self.get_response(request)

        # Check subscription
        try:
            subscription = request.school.subscription
        except Subscription.DoesNotExist:
            # No subscription at all - only allow billing endpoints
            return JsonResponse(
                {
                    'detail': 'No active subscription. Please subscribe to a plan.',
                    'code': 'no_subscription',
                },
                status=403,
            )

        # Attach subscription to request for use in views
        request.subscription = subscription

        # Check subscription status
        if subscription.is_active_or_trial:
            return self.get_response(request)

        if subscription.is_in_grace_period:
            # Allow read-only access during grace period
            if request.method not in ['GET', 'HEAD', 'OPTIONS']:
                return JsonResponse(
                    {
                        'detail': 'Subscription expired. Read-only access during grace period. Please renew.',
                        'code': 'grace_period',
                        'days_remaining': subscription.days_until_expiry,
                    },
                    status=403,
                )
            return self.get_response(request)

        # Subscription is expired/cancelled
        return JsonResponse(
            {
                'detail': 'Subscription expired. Please renew to continue.',
                'code': 'subscription_expired',
            },
            status=403,
        )

    def _is_exempt(self, request):
        for prefix in self.EXEMPT_URL_PREFIXES:
            if request.path.startswith(prefix):
                return True
        return False


def feature_required(feature_key):
    """
    Decorator for views that require a specific subscription feature.
    
    Usage:
        @feature_required('ai_tutor')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.is_platform_admin:
                return view_func(request, *args, **kwargs)

            subscription = getattr(request, 'subscription', None)
            if not subscription:
                return JsonResponse(
                    {'detail': 'No active subscription.', 'code': 'no_subscription'},
                    status=403,
                )

            if not subscription.has_feature(feature_key):
                return JsonResponse(
                    {
                        'detail': f'Feature "{feature_key}" is not available on your current plan. Please upgrade.',
                        'code': 'feature_not_available',
                        'feature': feature_key,
                        'current_plan': subscription.plan.name,
                    },
                    status=403,
                )

            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        wrapper.__doc__ = view_func.__doc__
        return wrapper
    return decorator
