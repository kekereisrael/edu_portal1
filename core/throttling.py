"""
Custom throttling classes for rate limiting.
Provides tiered rate limiting based on subscription plans and endpoint sensitivity.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """Short burst rate limit - prevents rapid-fire requests."""
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """Sustained rate limit - prevents abuse over longer periods."""
    scope = 'sustained'


class AnonBurstThrottle(AnonRateThrottle):
    """Rate limit for anonymous users - burst."""
    scope = 'anon_burst'


class AnonSustainedThrottle(AnonRateThrottle):
    """Rate limit for anonymous users - sustained."""
    scope = 'anon_sustained'


class LoginRateThrottle(AnonRateThrottle):
    """Strict rate limit for login attempts to prevent brute force."""
    scope = 'login'


class PasswordResetThrottle(AnonRateThrottle):
    """Rate limit for password reset requests."""
    scope = 'password_reset'


class EmailVerificationThrottle(UserRateThrottle):
    """Rate limit for email verification resend requests."""
    scope = 'email_verification'


class PaymentWebhookThrottle(SimpleRateThrottle):
    """Rate limit for payment webhook endpoints."""
    scope = 'payment_webhook'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


class AIUsageThrottle(UserRateThrottle):
    """Rate limit for AI-powered endpoints (expensive operations)."""
    scope = 'ai_usage'


class FileUploadThrottle(UserRateThrottle):
    """Rate limit for file upload endpoints."""
    scope = 'file_upload'


class ExamSubmissionThrottle(UserRateThrottle):
    """Rate limit for exam submission to prevent duplicate submissions."""
    scope = 'exam_submission'


class SubscriptionAwareThrottle(UserRateThrottle):
    """
    Dynamic throttle that adjusts rates based on the school's subscription plan.
    Premium plans get higher rate limits.
    """
    scope = 'subscription_aware'

    PLAN_RATES = {
        'free': '100/hour',
        'basic': '500/hour',
        'standard': '1000/hour',
        'premium': '5000/hour',
        'enterprise': '20000/hour',
    }

    def get_rate(self):
        if not self.request or not self.request.user or not self.request.user.is_authenticated:
            return '60/hour'

        # Try to get the school's subscription plan
        school = getattr(self.request, 'school', None)
        if school:
            try:
                subscription = school.subscription
                plan_name = subscription.plan.name.lower() if subscription and subscription.plan else 'free'
                return self.PLAN_RATES.get(plan_name, '100/hour')
            except Exception:
                pass

        return self.PLAN_RATES.get('free', '100/hour')

    def parse_rate(self, rate):
        """Parse the rate string."""
        if rate is None:
            return (None, None)
        num, period = rate.split('/')
        num_requests = int(num)
        duration = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(period[0], 3600)
        return (num_requests, duration)


class BulkOperationThrottle(UserRateThrottle):
    """Rate limit for bulk operations (imports, exports, mass notifications)."""
    scope = 'bulk_operation'


class SearchThrottle(UserRateThrottle):
    """Rate limit for search endpoints to prevent abuse."""
    scope = 'search'
