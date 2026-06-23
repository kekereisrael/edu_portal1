"""
Question Import Service — Phase 6B
Handles CSV, Excel (.xlsx), and bulk JSON import of questions into a QuestionBank.

CSV/Excel expected columns (case-insensitive, order-independent):
  question_text, question_type, option_a, option_b, option_c, option_d,
  correct_answer, explanation, difficulty, marks, topic_name,
  exam_category_code, exam_year, tags (comma-separated)

question_type values: mcq | true_false | short_answer  (default: mcq)
difficulty values:    easy | medium | hard              (default: medium)
correct_answer:       A/B/C/D for MCQ, True/False for T/F, text for short_answer
"""

import csv
import io
import logging
import uuid
from typing import IO, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Optional openpyxl import (Excel support) ─────────────────────────────────
try:
    import openpyxl
    EXCEL_SUPPORTED = True
except ImportError:
    EXCEL_SUPPORTED = False


# ─────────────────────────────────────────────────────────────────────────────
# Column normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {'question_text', 'correct_answer'}

COLUMN_ALIASES = {
    'question': 'question_text',
    'text': 'question_text',
    'q': 'question_text',
    'answer': 'correct_answer',
    'ans': 'correct_answer',
    'type': 'question_type',
    'diff': 'difficulty',
    'mark': 'marks',
    'point': 'marks',
    'points': 'marks',
    'topic': 'topic_name',
    'category': 'exam_category_code',
    'cat': 'exam_category_code',
    'year': 'exam_year',
    'tag': 'tags',
    'explain': 'explanation',
    'reason': 'explanation',
}


def _normalise_header(raw: str) -> str:
    """Lowercase, strip, and resolve aliases."""
    key = raw.strip().lower().replace(' ', '_').replace('-', '_')
    return COLUMN_ALIASES.get(key, key)


def _normalise_row(headers: List[str], values: List[str]) -> Dict[str, str]:
    """Zip headers with values, padding missing values with empty strings."""
    row = {}
    for i, h in enumerate(headers):
        row[h] = values[i].strip() if i < len(values) else ''
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Row → BankQuestion field mapping
# ─────────────────────────────────────────────────────────────────────────────

def _parse_row(row: Dict[str, str], bank, topic_cache: dict,
               tag_cache: dict, exam_cat_cache: dict) -> Tuple[dict, List[str]]:
    """
    Convert a normalised row dict into kwargs for BankQuestion.create().
    Returns (kwargs_dict, list_of_warnings).
    """
    from exams.models import BankQuestion, ExamCategory
    from subjects.models import Topic

    warnings = []

    question_text = row.get('question_text', '').strip()
    if not question_text:
        return None, ['Empty question_text — row skipped.']

    correct_answer = row.get('correct_answer', '').strip()
    if not correct_answer:
        return None, ['Empty correct_answer — row skipped.']

    # question_type
    raw_type = row.get('question_type', 'mcq').strip().lower().replace(' ', '_').replace('/', '_')
    type_map = {
        'mcq': BankQuestion.QuestionType.MCQ,
        'multiple_choice': BankQuestion.QuestionType.MCQ,
        'true_false': BankQuestion.QuestionType.TRUE_FALSE,
        'truefalse': BankQuestion.QuestionType.TRUE_FALSE,
        't_f': BankQuestion.QuestionType.TRUE_FALSE,
        'short_answer': BankQuestion.QuestionType.SHORT_ANSWER,
        'short': BankQuestion.QuestionType.SHORT_ANSWER,
    }
    question_type = type_map.get(raw_type, BankQuestion.QuestionType.MCQ)

    # difficulty
    raw_diff = row.get('difficulty', 'medium').strip().lower()
    diff_map = {
        'easy': BankQuestion.DifficultyLevel.EASY,
        'e': BankQuestion.DifficultyLevel.EASY,
        '1': BankQuestion.DifficultyLevel.EASY,
        'medium': BankQuestion.DifficultyLevel.MEDIUM,
        'med': BankQuestion.DifficultyLevel.MEDIUM,
        'm': BankQuestion.DifficultyLevel.MEDIUM,
        '2': BankQuestion.DifficultyLevel.MEDIUM,
        'hard': BankQuestion.DifficultyLevel.HARD,
        'h': BankQuestion.DifficultyLevel.HARD,
        'difficult': BankQuestion.DifficultyLevel.HARD,
        '3': BankQuestion.DifficultyLevel.HARD,
    }
    difficulty = diff_map.get(raw_diff, BankQuestion.DifficultyLevel.MEDIUM)

    # marks
    try:
        marks = max(1, int(row.get('marks', '1') or '1'))
    except ValueError:
        marks = 1
        warnings.append(f'Invalid marks value "{row.get("marks")}" — defaulting to 1.')

    # topic (lazy-loaded per bank subject)
    topic = None
    topic_name = row.get('topic_name', '').strip()
    if topic_name:
        if topic_name not in topic_cache:
            topic_obj = Topic.objects.filter(
                subject=bank.subject,
                name__iexact=topic_name,
            ).first()
            topic_cache[topic_name] = topic_obj
            if not topic_obj:
                warnings.append(f'Topic "{topic_name}" not found — field left blank.')
        topic = topic_cache[topic_name]

    # exam_category
    exam_category = None
    cat_code = row.get('exam_category_code', '').strip().lower()
    if cat_code:
        if cat_code not in exam_cat_cache:
            exam_cat_cache[cat_code] = ExamCategory.objects.filter(code=cat_code).first()
        exam_category = exam_cat_cache[cat_code]
        if not exam_category:
            warnings.append(f'ExamCategory code "{cat_code}" not found — field left blank.')

    # exam_year
    exam_year = None
    raw_year = row.get('exam_year', '').strip()
    if raw_year:
        try:
            exam_year = int(raw_year)
        except ValueError:
            warnings.append(f'Invalid exam_year "{raw_year}" — field left blank.')

    # tags (comma-separated)
    tag_names = [t.strip() for t in row.get('tags', '').split(',') if t.strip()]
    tag_objects = []
    for tag_name in tag_names:
        key = tag_name.lower()
        if key not in tag_cache:
            from exams.models import QuestionTag
            tag_obj, _ = QuestionTag.objects.get_or_create(
                school=bank.school,
                name__iexact=tag_name,
                defaults={'name': tag_name},
            )
            tag_cache[key] = tag_obj
        tag_objects.append(tag_cache[key])

    kwargs = {
        'bank': bank,
        'question_text': question_text,
        'question_type': question_type,
        'option_a': row.get('option_a', '') or None,
        'option_b': row.get('option_b', '') or None,
        'option_c': row.get('option_c', '') or None,
        'option_d': row.get('option_d', '') or None,
        'correct_answer': correct_answer,
        'explanation': row.get('explanation', '') or None,
        'difficulty': difficulty,
        'marks': marks,
        'topic': topic,
        'exam_category': exam_category,
        'exam_year': exam_year,
        '_tags': tag_objects,  # handled separately after create
    }
    return kwargs, warnings


# ─────────────────────────────────────────────────────────────────────────────
# Public import functions
# ─────────────────────────────────────────────────────────────────────────────

def import_from_csv(file_obj: IO, bank, import_batch: str = None) -> dict:
    """
    Import questions from a CSV file object into `bank`.
    Returns { 'created': int, 'skipped': int, 'warnings': list[str] }
    """
    from exams.models import BankQuestion

    batch = import_batch or str(uuid.uuid4())[:8]
    text = file_obj.read()
    if isinstance(text, bytes):
        text = text.decode('utf-8-sig')  # handle BOM

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return {'created': 0, 'skipped': 0, 'warnings': ['File is empty.']}

    headers = [_normalise_header(h) for h in rows[0]]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        return {
            'created': 0, 'skipped': 0,
            'warnings': [f'Missing required columns: {missing}'],
        }

    topic_cache, tag_cache, exam_cat_cache = {}, {}, {}
    created = skipped = 0
    all_warnings = []

    for line_no, raw_row in enumerate(rows[1:], start=2):
        if not any(v.strip() for v in raw_row):
            continue  # skip blank rows
        row = _normalise_row(headers, raw_row)
        kwargs, warnings = _parse_row(row, bank, topic_cache, tag_cache, exam_cat_cache)
        all_warnings += [f'Row {line_no}: {w}' for w in warnings]
        if kwargs is None:
            skipped += 1
            continue

        tags = kwargs.pop('_tags', [])
        bq = BankQuestion.objects.create(
            import_source='csv', import_batch=batch, **kwargs
        )
        if tags:
            bq.tags.set(tags)
        created += 1

    return {'created': created, 'skipped': skipped, 'warnings': all_warnings}


def import_from_excel(file_obj: IO, bank, import_batch: str = None) -> dict:
    """
    Import questions from an Excel (.xlsx) file object into `bank`.
    Reads the first worksheet.
    Returns { 'created': int, 'skipped': int, 'warnings': list[str] }
    """
    if not EXCEL_SUPPORTED:
        return {
            'created': 0, 'skipped': 0,
            'warnings': ['openpyxl is not installed. Excel import is unavailable.'],
        }

    from exams.models import BankQuestion

    batch = import_batch or str(uuid.uuid4())[:8]

    try:
        wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as exc:
        return {'created': 0, 'skipped': 0, 'warnings': [f'Failed to read Excel file: {exc}']}

    if not rows:
        return {'created': 0, 'skipped': 0, 'warnings': ['File is empty.']}

    headers = [_normalise_header(str(h) if h is not None else '') for h in rows[0]]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        return {
            'created': 0, 'skipped': 0,
            'warnings': [f'Missing required columns: {missing}'],
        }

    topic_cache, tag_cache, exam_cat_cache = {}, {}, {}
    created = skipped = 0
    all_warnings = []

    for line_no, raw_row in enumerate(rows[1:], start=2):
        str_row = [str(v).strip() if v is not None else '' for v in raw_row]
        if not any(str_row):
            continue
        row = _normalise_row(headers, str_row)
        kwargs, warnings = _parse_row(row, bank, topic_cache, tag_cache, exam_cat_cache)
        all_warnings += [f'Row {line_no}: {w}' for w in warnings]
        if kwargs is None:
            skipped += 1
            continue

        tags = kwargs.pop('_tags', [])
        bq = BankQuestion.objects.create(
            import_source='excel', import_batch=batch, **kwargs
        )
        if tags:
            bq.tags.set(tags)
        created += 1

    return {'created': created, 'skipped': skipped, 'warnings': all_warnings}


def import_from_json(data: list, bank, import_batch: str = None) -> dict:
    """
    Import questions from a list of dicts (JSON body) into `bank`.
    Each dict must have at minimum: question_text, correct_answer.
    Returns { 'created': int, 'skipped': int, 'warnings': list[str] }
    """
    from exams.models import BankQuestion

    batch = import_batch or str(uuid.uuid4())[:8]
    topic_cache, tag_cache, exam_cat_cache = {}, {}, {}
    created = skipped = 0
    all_warnings = []

    for idx, raw in enumerate(data, start=1):
        # Normalise keys
        row = {_normalise_header(k): str(v).strip() if v is not None else '' for k, v in raw.items()}
        kwargs, warnings = _parse_row(row, bank, topic_cache, tag_cache, exam_cat_cache)
        all_warnings += [f'Item {idx}: {w}' for w in warnings]
        if kwargs is None:
            skipped += 1
            continue

        tags = kwargs.pop('_tags', [])
        bq = BankQuestion.objects.create(
            import_source='json', import_batch=batch, **kwargs
        )
        if tags:
            bq.tags.set(tags)
        created += 1

    return {'created': created, 'skipped': skipped, 'warnings': all_warnings}
