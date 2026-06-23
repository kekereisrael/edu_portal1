"""Script to drop old exam tables from SQLite database."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'exams_%'")
tables = [row[0] for row in cursor.fetchall()]
print('Found exam tables:', tables)

for t in tables:
    try:
        cursor.execute(f'DROP TABLE IF EXISTS "{t}"')
        print(f'Dropped: {t}')
    except Exception as e:
        print(f'Error dropping {t}: {e}')

connection.commit()
print('Done!')
