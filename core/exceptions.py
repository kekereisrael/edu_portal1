"""
Custom exception handler for consistent API error responses.
Provides structured error responses with error codes and details.
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.exceptions import (
    APIException, ValidationError, NotAuthenticated,
    PermissionDenied, NotFound, Throttled
)
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.http import Http404

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error response format.
    
    Response format:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {} or []  # Optional additional details
        }
    }
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        error_data = _format_error_response(exc, response)
        response.data = error_data
        return response

    # Handle exceptions not caught by DRF
    if isinstance(exc, ObjectDoesNotExist):
        error_data = {
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'The requested resource was not found.',
                'details': None,
            }
        }
        return Response(error_data, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, IntegrityError):
        logger.error(f"Database integrity error: {exc}", exc_info=True)
        error_data = {
            'success': False,
            'error': {
                'code': 'INTEGRITY_ERROR',
                'message': 'A database constraint was violated. This may be a duplicate entry.',
                'details': None,
            }
        }
        return Response(error_data, status=status.HTTP_409_CONFLICT)

    # Log unexpected exceptions
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return None


def _format_error_response(exc, response):
    """Format the error response based on exception type."""

    if isinstance(exc, ValidationError):
        return {
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'The request data is invalid.',
                'details': response.data,
            }
        }

    if isinstance(exc, NotAuthenticated):
        return {
            'success': False,
            'error': {
                'code': 'NOT_AUTHENTICATED',
                'message': 'Authentication credentials were not provided or are invalid.',
                'details': None,
            }
        }

    if isinstance(exc, PermissionDenied):
        return {
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(exc.detail) if exc.detail else 'You do not have permission to perform this action.',
                'details': None,
            }
        }

    if isinstance(exc, NotFound) or isinstance(exc, Http404):
        return {
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'The requested resource was not found.',
                'details': None,
            }
        }

    if isinstance(exc, Throttled):
        return {
            'success': False,
            'error': {
                'code': 'RATE_LIMITED',
                'message': f'Request was throttled. Please try again in {exc.wait} seconds.',
                'details': {
                    'retry_after': exc.wait,
                },
            }
        }

    # Generic API exception
    error_code = getattr(exc, 'default_code', 'ERROR')
    return {
        'success': False,
        'error': {
            'code': error_code.upper() if isinstance(error_code, str) else 'ERROR',
            'message': str(exc.detail) if hasattr(exc, 'detail') else 'An error occurred.',
            'details': response.data if response.data != {'detail': str(getattr(exc, 'detail', ''))} else None,
        }
    }


# Custom Exception Classes

class SchoolContextRequired(APIException):
    """Raised when a request requires school context but none is provided."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'School context is required. Provide X-School-ID header.'
    default_code = 'school_context_required'


class SubscriptionRequired(APIException):
    """Raised when a feature requires an active subscription."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'An active subscription is required to access this feature.'
    default_code = 'subscription_required'


class SubscriptionLimitExceeded(APIException):
    """Raised when a subscription limit is exceeded."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Your subscription plan limit has been exceeded. Please upgrade.'
    default_code = 'subscription_limit_exceeded'


class StorageQuotaExceeded(APIException):
    """Raised when storage quota is exceeded."""
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = 'Storage quota exceeded. Please upgrade your plan or delete unused files.'
    default_code = 'storage_quota_exceeded'


class ExamNotAvailable(APIException):
    """Raised when an exam is not available for the student."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This exam is not currently available.'
    default_code = 'exam_not_available'


class ExamAlreadySubmitted(APIException):
    """Raised when trying to modify an already submitted exam."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This exam attempt has already been submitted.'
    default_code = 'exam_already_submitted'


class ExamTimeExpired(APIException):
    """Raised when exam time has expired."""
    status_code = status.HTTP_410_GONE
    default_detail = 'The time allocated for this exam has expired.'
    default_code = 'exam_time_expired'


class PaymentFailed(APIException):
    """Raised when a payment operation fails."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment processing failed. Please try again.'
    default_code = 'payment_failed'


class DuplicateWebhookEvent(APIException):
    """Raised when a duplicate webhook event is received."""
    status_code = status.HTTP_200_OK  # Return 200 to prevent retries
    default_detail = 'Event already processed.'
    default_code = 'duplicate_event'


class InvalidFileType(APIException):
    """Raised when an uploaded file type is not allowed."""
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = 'The uploaded file type is not supported.'
    default_code = 'invalid_file_type'


class AIServiceUnavailable(APIException):
    """Raised when AI/LLM service is unavailable."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'AI service is temporarily unavailable. Please try again later.'
    default_code = 'ai_service_unavailable'
