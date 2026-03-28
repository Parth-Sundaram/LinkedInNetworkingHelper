"""
dedup_references.py — Keeps only the highest-priority role per company
in Internship_References.csv, since references are the same across roles.

Run: python3 dedup_references.py
"""

import csv
import os

INPUT  = os.path.join('Sprint_Targets', 'Internship_References.csv')
OUTPUT = os.path.join('Sprint_Targets', 'Internship_References.csv')

with open(INPUT, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

before = len(rows)

# Keep the first occurrence of each company (CSV is sorted by priority descending
# so the first one is already the highest priority role)
seen = set()
deduped = []
for row in rows:
    company = row.get('Company', '').strip().lower()
    if company not in seen:
        seen.add(company)
        deduped.append(row)

after = len(deduped)

with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(deduped)

print(f"Removed {before - after} duplicate company entries. {after} remaining.")
