"""
Management command to seed initial subscription plans.
"""

from django.core.management.base import BaseCommand

from subscriptions.models import Plan, PlanFeature


class Command(BaseCommand):
    help = 'Seed initial subscription plans and features'

    def handle(self, *args, **options):
        self.stdout.write('Seeding subscription plans...')

        plans_data = [
            {
                'name': Plan.PlanName.FREE,
                'display_name': 'Free Plan',
                'description': 'Get started with basic exam features for small schools.',
                'price_monthly': 0,
                'price_yearly': 0,
                'max_students': 50,
                'max_teachers': 5,
                'max_storage_gb': 1,
                'ai_credits_monthly': 0,
                'sort_order': 1,
                'features': {
                    'basic_exams': True,
                    'materials': False,
                    'results': False,
                    'analytics': False,
                    'parent_portal': False,
                    'ai_tutor': False,
                    'ai_exam_generator': False,
                    'ai_essay_grading': False,
                    'proctoring': False,
                    'api_access': False,
                },
            },
            {
                'name': Plan.PlanName.BASIC,
                'display_name': 'Basic Plan',
                'description': 'Essential features for growing schools.',
                'price_monthly': 15000,
                'price_yearly': 144000,
                'max_students': 200,
                'max_teachers': 20,
                'max_storage_gb': 10,
                'ai_credits_monthly': 0,
                'sort_order': 2,
                'features': {
                    'basic_exams': True,
                    'materials': True,
                    'results': True,
                    'analytics': False,
                    'parent_portal': False,
                    'ai_tutor': False,
                    'ai_exam_generator': False,
                    'ai_essay_grading': False,
                    'proctoring': False,
                    'api_access': False,
                },
            },
            {
                'name': Plan.PlanName.STANDARD,
                'display_name': 'Standard Plan',
                'description': 'Advanced features with analytics and parent portal.',
                'price_monthly': 45000,
                'price_yearly': 432000,
                'max_students': 1000,
                'max_teachers': 50,
                'max_storage_gb': 50,
                'ai_credits_monthly': 100,
                'sort_order': 3,
                'features': {
                    'basic_exams': True,
                    'materials': True,
                    'results': True,
                    'analytics': True,
                    'parent_portal': True,
                    'ai_tutor': False,
                    'ai_exam_generator': False,
                    'ai_essay_grading': False,
                    'proctoring': True,
                    'api_access': False,
                },
            },
            {
                'name': Plan.PlanName.PREMIUM,
                'display_name': 'Premium Plan',
                'description': 'Full AI-powered features for large schools.',
                'price_monthly': 100000,
                'price_yearly': 960000,
                'max_students': 5000,
                'max_teachers': 200,
                'max_storage_gb': 200,
                'ai_credits_monthly': 1000,
                'sort_order': 4,
                'features': {
                    'basic_exams': True,
                    'materials': True,
                    'results': True,
                    'analytics': True,
                    'parent_portal': True,
                    'ai_tutor': True,
                    'ai_exam_generator': True,
                    'ai_essay_grading': True,
                    'proctoring': True,
                    'api_access': True,
                },
            },
            {
                'name': Plan.PlanName.ENTERPRISE,
                'display_name': 'Enterprise Plan',
                'description': 'Unlimited access with dedicated support and white-label options.',
                'price_monthly': 300000,
                'price_yearly': 2880000,
                'max_students': -1,
                'max_teachers': -1,
                'max_storage_gb': 1000,
                'ai_credits_monthly': 5000,
                'sort_order': 5,
                'features': {
                    'basic_exams': True,
                    'materials': True,
                    'results': True,
                    'analytics': True,
                    'parent_portal': True,
                    'ai_tutor': True,
                    'ai_exam_generator': True,
                    'ai_essay_grading': True,
                    'proctoring': True,
                    'api_access': True,
                    'white_label': True,
                    'custom_reports': True,
                },
            },
        ]

        feature_names = {
            'basic_exams': 'Basic Exams',
            'materials': 'Learning Materials',
            'results': 'Detailed Results',
            'analytics': 'Analytics Dashboard',
            'parent_portal': 'Parent Portal',
            'ai_tutor': 'AI Tutor',
            'ai_exam_generator': 'AI Exam Generator',
            'ai_essay_grading': 'AI Essay Grading',
            'proctoring': 'Exam Proctoring',
            'api_access': 'API Access',
            'white_label': 'White Label',
            'custom_reports': 'Custom Reports',
        }

        for plan_data in plans_data:
            features = plan_data.pop('features')
            plan, created = Plan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data,
            )

            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action}: {plan.display_name}')

            # Create/update plan features
            plan.features = features
            plan.save(update_fields=['features'])

            for feature_key, is_enabled in features.items():
                PlanFeature.objects.update_or_create(
                    plan=plan,
                    feature_key=feature_key,
                    defaults={
                        'feature_name': feature_names.get(feature_key, feature_key),
                        'is_enabled': is_enabled,
                    },
                )

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(plans_data)} plans.'))
