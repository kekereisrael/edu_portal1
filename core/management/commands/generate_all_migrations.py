"""
Management command to verify schema integrity and generate migrations.
Run with: python manage.py generate_all_migrations
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
import sys


class Command(BaseCommand):
    help = 'Generate migrations for all apps and verify schema integrity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Check for missing migrations without creating them',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what migrations would be created without creating them',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE('Educational Portal - Migration Generator'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        local_apps = [
            'core',
            'accounts',
            'schools',
            'subscriptions',
            'subjects',
            'exams',
            'materials',
            'notifications',
            'payments',
            'analytics',
            'communications',
        ]

        if options['check']:
            self.stdout.write('\nChecking for missing migrations...\n')
            try:
                call_command('makemigrations', '--check', '--dry-run')
                self.stdout.write(self.style.SUCCESS('No missing migrations'))
            except SystemExit:
                self.stdout.write(self.style.ERROR('Missing migrations detected'))
                sys.exit(1)
            return

        # Generate migrations for each app
        self.stdout.write('\nGenerating migrations for all apps...\n')

        for app_name in local_apps:
            try:
                self.stdout.write(f'  Processing {app_name}...')
                if options['dry_run']:
                    call_command('makemigrations', app_name, '--dry-run', verbosity=0)
                else:
                    call_command('makemigrations', app_name, verbosity=0)
                self.stdout.write(self.style.SUCCESS(f'  Done: {app_name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Failed: {app_name}: {e}'))

        # Show migration plan
        self.stdout.write('\nMigration plan:\n')
        call_command('showmigrations', *local_apps, verbosity=1)

        self.stdout.write(self.style.SUCCESS('\nMigration generation complete'))
