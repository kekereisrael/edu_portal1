# Generated data migration — seeds standard Nigerian exam categories

from django.db import migrations


EXAM_CATEGORIES = [
    {
        'code': 'school_exam',
        'name': 'School Exam',
        'description': 'Internal school examinations (CA, mid-term, end-of-term).',
        'is_public': False,
    },
    {
        'code': 'waec',
        'name': 'WAEC',
        'description': 'West African Examinations Council — WASSCE / GCE.',
        'is_public': True,
    },
    {
        'code': 'neco',
        'name': 'NECO',
        'description': 'National Examinations Council — SSCE / GCE.',
        'is_public': True,
    },
    {
        'code': 'jamb',
        'name': 'JAMB (UTME)',
        'description': 'Joint Admissions and Matriculation Board — Unified Tertiary Matriculation Examination.',
        'is_public': True,
    },
    {
        'code': 'bece',
        'name': 'BECE',
        'description': 'Basic Education Certificate Examination (JSS3 exit exam).',
        'is_public': True,
    },
    {
        'code': 'nabteb',
        'name': 'NABTEB',
        'description': 'National Business and Technical Examinations Board.',
        'is_public': True,
    },
    {
        'code': 'mock',
        'name': 'Mock Exam',
        'description': 'Mock / trial examinations in preparation for public exams.',
        'is_public': False,
    },
    {
        'code': 'practice',
        'name': 'Practice / Revision',
        'description': 'Practice questions and revision exercises.',
        'is_public': False,
    },
]


def seed_exam_categories(apps, schema_editor):
    ExamCategory = apps.get_model('exams', 'ExamCategory')
    for cat in EXAM_CATEGORIES:
        ExamCategory.objects.get_or_create(
            code=cat['code'],
            defaults={
                'name': cat['name'],
                'description': cat['description'],
                'is_public': cat['is_public'],
                'is_active': True,
            },
        )


def remove_exam_categories(apps, schema_editor):
    ExamCategory = apps.get_model('exams', 'ExamCategory')
    codes = [c['code'] for c in EXAM_CATEGORIES]
    ExamCategory.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0003_phase6b_question_bank'),
    ]

    operations = [
        migrations.RunPython(seed_exam_categories, remove_exam_categories),
    ]
