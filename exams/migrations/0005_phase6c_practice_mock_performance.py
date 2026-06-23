"""
Phase 6C — Practice Mode, Mock Exams & Student Improvement

New models:
  - PracticeSession
  - PracticeAnswer
  - MockExamSession
  - MockExamAnswer
  - TopicPerformance
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0004_seed_exam_categories'),
        ('subjects', '0001_initial'),
        ('schools', '0003_phase6a_academic_structure'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── PracticeSession ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='PracticeSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('difficulty', models.CharField(
                    blank=True, choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
                    max_length=10, null=True,
                )),
                ('question_type', models.CharField(
                    blank=True,
                    choices=[('mcq', 'Multiple Choice'), ('true_false', 'True/False'), ('short_answer', 'Short Answer')],
                    max_length=20, null=True,
                )),
                ('num_questions', models.PositiveSmallIntegerField(default=10)),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('completed', 'Completed'), ('abandoned', 'Abandoned')],
                    db_index=True, default='active', max_length=20,
                )),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('bank', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='practice_sessions', to='exams.questionbank',
                )),
                ('student', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='practice_sessions', to=settings.AUTH_USER_MODEL,
                )),
                ('topic', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='practice_sessions', to='subjects.topic',
                )),
            ],
            options={
                'verbose_name': 'practice session',
                'verbose_name_plural': 'practice sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='practicesession',
            index=models.Index(fields=['student', 'bank'], name='idx_practice_student_bank'),
        ),
        migrations.AddIndex(
            model_name='practicesession',
            index=models.Index(fields=['student', 'status'], name='idx_practice_student_status'),
        ),

        # ── PracticeAnswer ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='PracticeAnswer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('selected_answer', models.CharField(blank=True, max_length=500, null=True)),
                ('is_correct', models.BooleanField(blank=True, null=True)),
                ('time_spent_seconds', models.IntegerField(default=0)),
                ('bank_question', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='practice_answers', to='exams.bankquestion',
                )),
                ('session', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='practice_answers', to='exams.practicesession',
                )),
            ],
            options={
                'verbose_name': 'practice answer',
                'verbose_name_plural': 'practice answers',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='practiceanswer',
            index=models.Index(fields=['session', 'bank_question'], name='idx_pans_session_bq'),
        ),
        migrations.AddIndex(
            model_name='practiceanswer',
            index=models.Index(fields=['session', 'is_correct'], name='idx_pans_session_correct'),
        ),

        # ── MockExamSession ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='MockExamSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('difficulty', models.CharField(
                    blank=True, choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
                    max_length=10, null=True,
                )),
                ('num_questions', models.PositiveSmallIntegerField(default=40)),
                ('duration_minutes', models.PositiveSmallIntegerField(default=60)),
                ('passing_score', models.DecimalField(decimal_places=2, default=50.0, max_digits=5)),
                ('shuffle_questions', models.BooleanField(default=True)),
                ('status', models.CharField(
                    choices=[
                        ('in_progress', 'In Progress'), ('submitted', 'Submitted'),
                        ('timed_out', 'Timed Out'), ('abandoned', 'Abandoned'),
                    ],
                    db_index=True, default='in_progress', max_length=20,
                )),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('time_taken_seconds', models.IntegerField(default=0)),
                ('score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('percentage', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('passed', models.BooleanField(blank=True, null=True)),
                ('total_questions', models.IntegerField(default=0)),
                ('correct_answers', models.IntegerField(default=0)),
                ('wrong_answers', models.IntegerField(default=0)),
                ('skipped_answers', models.IntegerField(default=0)),
                ('bank', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='mock_exam_sessions', to='exams.questionbank',
                )),
                ('exam_category', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='mock_exam_sessions', to='exams.examcategory',
                )),
                ('student', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='mock_exam_sessions', to=settings.AUTH_USER_MODEL,
                )),
                ('topic', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='mock_exam_sessions', to='subjects.topic',
                )),
            ],
            options={
                'verbose_name': 'mock exam session',
                'verbose_name_plural': 'mock exam sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='mockexamsession',
            index=models.Index(fields=['student', 'bank'], name='idx_mock_student_bank'),
        ),
        migrations.AddIndex(
            model_name='mockexamsession',
            index=models.Index(fields=['student', 'status'], name='idx_mock_student_status'),
        ),

        # ── MockExamAnswer ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='MockExamAnswer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('selected_answer', models.CharField(blank=True, max_length=500, null=True)),
                ('is_correct', models.BooleanField(blank=True, null=True)),
                ('is_marked_for_review', models.BooleanField(default=False)),
                ('time_spent_seconds', models.IntegerField(default=0)),
                ('answered_at', models.DateTimeField(blank=True, null=True)),
                ('bank_question', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='mock_answers', to='exams.bankquestion',
                )),
                ('session', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='mock_answers', to='exams.mockexamsession',
                )),
            ],
            options={
                'verbose_name': 'mock exam answer',
                'verbose_name_plural': 'mock exam answers',
                'ordering': ['created_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='mockexamanswer',
            unique_together={('session', 'bank_question')},
        ),
        migrations.AddIndex(
            model_name='mockexamanswer',
            index=models.Index(fields=['session', 'is_correct'], name='idx_mans_session_correct'),
        ),

        # ── TopicPerformance ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='TopicPerformance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('total_attempts', models.PositiveIntegerField(default=0)),
                ('total_correct', models.PositiveIntegerField(default=0)),
                ('total_wrong', models.PositiveIntegerField(default=0)),
                ('accuracy_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('strength_level', models.CharField(
                    choices=[('weak', 'Weak'), ('average', 'Average'), ('strong', 'Strong')],
                    db_index=True, default='average', max_length=10,
                )),
                ('last_practiced_at', models.DateTimeField(blank=True, null=True)),
                ('school', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='topic_performances', to='schools.school',
                )),
                ('student', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='topic_performances', to=settings.AUTH_USER_MODEL,
                )),
                ('subject', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='topic_performances', to='subjects.subject',
                )),
                ('topic', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='performances', to='subjects.topic',
                )),
            ],
            options={
                'verbose_name': 'topic performance',
                'verbose_name_plural': 'topic performances',
                'ordering': ['accuracy_percent'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='topicperformance',
            unique_together={('student', 'topic')},
        ),
        migrations.AddIndex(
            model_name='topicperformance',
            index=models.Index(
                fields=['student', 'school', 'strength_level'],
                name='idx_tp_student_school_strength',
            ),
        ),
        migrations.AddIndex(
            model_name='topicperformance',
            index=models.Index(fields=['student', 'subject'], name='idx_tp_student_subject'),
        ),
    ]
