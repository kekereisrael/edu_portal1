"""
Initial migration for the achievements app.
Phase 6D: Leaderboards, Badges & Achievements.

Models:
  - Badge
  - StudentBadge
  - LeaderboardEntry
"""

import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('schools', '0001_initial'),
        ('subjects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Badge ─────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('badge_type', models.CharField(
                    choices=[
                        ('first_exam', 'First Exam Completed'),
                        ('perfect_score', 'Perfect Score'),
                        ('top_performer', 'Top Performer'),
                        ('pass_streak', 'Pass Streak'),
                        ('math_genius', 'Math Genius'),
                        ('science_star', 'Science Star'),
                        ('english_master', 'English Master'),
                        ('subject_master', 'Subject Master'),
                        ('practice_champion', 'Practice Champion'),
                        ('consistent_learner', 'Consistent Learner'),
                        ('speed_demon', 'Speed Demon'),
                        ('mock_master', 'Mock Exam Master'),
                        ('first_mock', 'First Mock Exam'),
                        ('most_improved', 'Most Improved'),
                        ('comeback_kid', 'Comeback Kid'),
                        ('custom', 'Custom Badge'),
                    ],
                    db_index=True,
                    max_length=30,
                )),
                ('tier', models.CharField(
                    choices=[
                        ('bronze', 'Bronze'),
                        ('silver', 'Silver'),
                        ('gold', 'Gold'),
                        ('platinum', 'Platinum'),
                    ],
                    default='bronze',
                    max_length=10,
                )),
                ('description', models.TextField()),
                ('icon', models.CharField(
                    default='🏅',
                    help_text='Emoji or icon identifier for the badge',
                    max_length=50,
                )),
                ('criteria', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='e.g. {"min_score": 100, "subject_code": "MATH"}',
                )),
                ('is_global', models.BooleanField(
                    default=True,
                    help_text='Global badges are available to all schools',
                )),
                ('school', models.ForeignKey(
                    blank=True,
                    help_text='Set only for school-specific custom badges',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='custom_badges',
                    to='schools.school',
                )),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'badge',
                'verbose_name_plural': 'badges',
                'ordering': ['tier', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='badge',
            index=models.Index(fields=['badge_type', 'is_active'], name='idx_badge_type_active'),
        ),

        # ── StudentBadge ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='StudentBadge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='earned_badges',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('badge', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='awarded_to',
                    to='achievements.badge',
                )),
                ('school', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_badges',
                    to='schools.school',
                )),
                ('awarded_for', models.CharField(
                    blank=True,
                    help_text='Human-readable reason, e.g. "Scored 100% in MATH101 exam"',
                    max_length=200,
                )),
                ('related_object_type', models.CharField(blank=True, max_length=50, null=True)),
                ('related_object_id', models.UUIDField(blank=True, null=True)),
                ('awarded_at', models.DateTimeField(auto_now_add=True)),
                ('is_seen', models.BooleanField(db_index=True, default=False)),
            ],
            options={
                'verbose_name': 'student badge',
                'verbose_name_plural': 'student badges',
                'ordering': ['-awarded_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='studentbadge',
            unique_together={('student', 'badge')},
        ),
        migrations.AddIndex(
            model_name='studentbadge',
            index=models.Index(fields=['student', 'school'], name='idx_sb_student_school'),
        ),
        migrations.AddIndex(
            model_name='studentbadge',
            index=models.Index(fields=['student', 'is_seen'], name='idx_sb_student_seen'),
        ),

        # ── LeaderboardEntry ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='LeaderboardEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='leaderboard_entries',
                    to='schools.school',
                )),
                ('term', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='leaderboard_entries',
                    to='schools.term',
                )),
                ('leaderboard_type', models.CharField(
                    choices=[
                        ('school', 'School'),
                        ('class', 'Class'),
                        ('subject', 'Subject'),
                    ],
                    db_index=True,
                    max_length=10,
                )),
                ('classroom', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='leaderboard_entries',
                    to='schools.classroom',
                )),
                ('subject', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='leaderboard_entries',
                    to='subjects.subject',
                )),
                ('student', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='leaderboard_entries',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('rank', models.PositiveIntegerField(db_index=True, default=0)),
                ('highest_score', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Best exam percentage in scope',
                    max_digits=5,
                )),
                ('average_score', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Average exam percentage in scope',
                    max_digits=5,
                )),
                ('total_exams', models.PositiveIntegerField(default=0)),
                ('total_practice', models.PositiveIntegerField(
                    default=0,
                    help_text='Practice sessions completed',
                )),
                ('activity_score', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Composite score: avg_score * 0.6 + activity_bonus * 0.4',
                    max_digits=7,
                )),
                ('calculated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'leaderboard entry',
                'verbose_name_plural': 'leaderboard entries',
                'ordering': ['rank'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='leaderboardentry',
            unique_together={('school', 'term', 'leaderboard_type', 'classroom', 'subject', 'student')},
        ),
        migrations.AddIndex(
            model_name='leaderboardentry',
            index=models.Index(
                fields=['school', 'term', 'leaderboard_type', 'rank'],
                name='idx_lb_school_term_type_rank',
            ),
        ),
        migrations.AddIndex(
            model_name='leaderboardentry',
            index=models.Index(
                fields=['school', 'leaderboard_type', 'classroom'],
                name='idx_lb_school_type_class',
            ),
        ),
        migrations.AddIndex(
            model_name='leaderboardentry',
            index=models.Index(
                fields=['school', 'leaderboard_type', 'subject'],
                name='idx_lb_school_type_subject',
            ),
        ),
    ]
