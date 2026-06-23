# Generated migration for exams app - new model structure

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models  # noqa: F401


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('schools', '0002_storageusage'),
        ('subjects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('exam_type', models.CharField(
                    choices=[('cbt', 'Computer-Based Test'), ('quiz', 'Quiz'), ('practice', 'Practice Test'), ('assignment', 'Assignment')],
                    default='cbt', max_length=20, db_index=True
                )),
                ('status', models.CharField(
                    choices=[('draft', 'Draft'), ('published', 'Published'), ('active', 'Active'), ('closed', 'Closed'), ('archived', 'Archived')],
                    default='draft', max_length=20, db_index=True
                )),
                ('instructions', models.TextField(blank=True, null=True)),
                ('duration_minutes', models.IntegerField(default=60)),
                ('passing_score', models.DecimalField(decimal_places=2, default=50.0, max_digits=5)),
                ('total_marks', models.IntegerField(default=0)),
                ('shuffle_questions', models.BooleanField(default=False)),
                ('shuffle_options', models.BooleanField(default=False)),
                ('show_result_immediately', models.BooleanField(default=True)),
                ('allow_review', models.BooleanField(default=True)),
                ('max_attempts', models.IntegerField(default=1)),
                ('start_date', models.DateTimeField(blank=True, null=True)),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='schools.school')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exams', to='subjects.subject', db_index=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_exams', to=settings.AUTH_USER_MODEL, db_index=True)),
                ('term', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exams', to='schools.term')),
            ],
            options={'verbose_name': 'exam', 'verbose_name_plural': 'exams', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='exam',
            index=models.Index(fields=['school', 'status'], name='idx_exam_school_status'),
        ),
        migrations.AddIndex(
            model_name='exam',
            index=models.Index(fields=['school', 'subject'], name='idx_exam_school_subject'),
        ),
        migrations.AddIndex(
            model_name='exam',
            index=models.Index(fields=['created_by', 'status'], name='idx_exam_creator_status'),
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('question_text', models.TextField()),
                ('question_type', models.CharField(
                    choices=[('mcq', 'Multiple Choice'), ('true_false', 'True/False'), ('short_answer', 'Short Answer')],
                    default='mcq', max_length=20
                )),
                ('option_a', models.CharField(blank=True, max_length=500, null=True)),
                ('option_b', models.CharField(blank=True, max_length=500, null=True)),
                ('option_c', models.CharField(blank=True, max_length=500, null=True)),
                ('option_d', models.CharField(blank=True, max_length=500, null=True)),
                ('correct_answer', models.CharField(max_length=10)),
                ('explanation', models.TextField(blank=True, null=True)),
                ('difficulty', models.CharField(
                    choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
                    default='medium', max_length=10
                )),
                ('marks', models.IntegerField(default=1)),
                ('order', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='exams.exam', db_index=True)),
                ('topic', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='subjects.topic')),
            ],
            options={'verbose_name': 'question', 'verbose_name_plural': 'questions', 'ordering': ['order', 'created_at']},
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['exam', 'is_active'], name='idx_question_exam_active'),
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['exam', 'difficulty'], name='idx_question_exam_diff'),
        ),
        migrations.CreateModel(
            name='ExamAttempt',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[('in_progress', 'In Progress'), ('submitted', 'Submitted'), ('timed_out', 'Timed Out'), ('graded', 'Graded'), ('abandoned', 'Abandoned')],
                    default='in_progress', max_length=20, db_index=True
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
                ('attempt_number', models.IntegerField(default=1)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='exams.exam', db_index=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_attempts', to=settings.AUTH_USER_MODEL, db_index=True)),
            ],
            options={'verbose_name': 'exam attempt', 'verbose_name_plural': 'exam attempts', 'ordering': ['-started_at']},
        ),
        migrations.AddIndex(
            model_name='examattempt',
            index=models.Index(fields=['student', 'exam'], name='idx_attempt_student_exam'),
        ),
        migrations.AddIndex(
            model_name='examattempt',
            index=models.Index(fields=['exam', 'status'], name='idx_attempt_exam_status'),
        ),
        migrations.AddIndex(
            model_name='examattempt',
            index=models.Index(fields=['student', 'status'], name='idx_attempt_student_status'),
        ),
        migrations.CreateModel(
            name='ExamAnswer',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('selected_answer', models.CharField(blank=True, max_length=500, null=True)),
                ('is_correct', models.BooleanField(blank=True, null=True)),
                ('is_marked_for_review', models.BooleanField(default=False)),
                ('time_spent_seconds', models.IntegerField(default=0)),
                ('answered_at', models.DateTimeField(blank=True, null=True)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='exams.examattempt', db_index=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_answers', to='exams.question', db_index=True)),
            ],
            options={'verbose_name': 'exam answer', 'verbose_name_plural': 'exam answers'},
        ),
        migrations.AlterUniqueTogether(
            name='examanswer',
            unique_together={('attempt', 'question')},
        ),
        migrations.AddIndex(
            model_name='examanswer',
            index=models.Index(fields=['attempt', 'is_correct'], name='idx_answer_attempt_correct'),
        ),
        migrations.CreateModel(
            name='ExamResult',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('score', models.DecimalField(decimal_places=2, max_digits=5)),
                ('percentage', models.DecimalField(decimal_places=2, max_digits=5)),
                ('passed', models.BooleanField()),
                ('grade', models.CharField(blank=True, max_length=5, null=True)),
                ('rank', models.IntegerField(blank=True, null=True)),
                ('feedback', models.TextField(blank=True, null=True)),
                ('attempt', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='result', to='exams.examattempt')),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='exams.exam', db_index=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_results', to=settings.AUTH_USER_MODEL, db_index=True)),
            ],
            options={'verbose_name': 'exam result', 'verbose_name_plural': 'exam results', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='examresult',
            index=models.Index(fields=['student', 'exam'], name='idx_result_student_exam'),
        ),
        migrations.AddIndex(
            model_name='examresult',
            index=models.Index(fields=['exam', 'percentage'], name='idx_result_exam_pct'),
        ),
    ]
