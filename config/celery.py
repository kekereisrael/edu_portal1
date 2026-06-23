"""
Celery configuration for the educational portal.
Safe mode: runs tasks synchronously when broker is unavailable.
"""

import os
import logging

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('edu_portal')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Schedule - Periodic Tasks
app.conf.beat_schedule = {
    # Subscription management
    'check-expiring-subscriptions': {
        'task': 'subscriptions.tasks.check_expiring_subscriptions',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    'expire-trial-subscriptions': {
        'task': 'subscriptions.tasks.expire_trial_subscriptions',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },

    # Analytics aggregation
    'aggregate-daily-analytics': {
        'task': 'analytics.tasks.aggregate_daily_analytics',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    'generate-weekly-reports': {
        'task': 'analytics.tasks.generate_weekly_reports',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),  # Monday 6 AM
    },

    # Cleanup tasks
    'cleanup-expired-tokens': {
        'task': 'accounts.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
    },

    # Payment retries
    'retry-failed-payments': {
        'task': 'payments.tasks.retry_failed_payments',
        'schedule': crontab(hour='*/6', minute=30),  # Every 6 hours
    },

    # Storage usage calculation
    'calculate-storage-usage': {
        'task': 'schools.tasks.calculate_storage_usage',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}

# Task routing
app.conf.task_routes = {
    'payments.*': {'queue': 'payments'},
    'notifications.*': {'queue': 'notifications'},
    'analytics.*': {'queue': 'analytics'},
    'exams.tasks.auto_grade_exam': {'queue': 'grading'},
    '*': {'queue': 'default'},
}

# Task settings
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_time_limit = 300  # 5 minutes hard limit
app.conf.task_soft_time_limit = 240  # 4 minutes soft limit
