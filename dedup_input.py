"""
dedup_input.py — Keeps only the highest-priority role per company in
Internships_Recomputed_Clean.csv so people_finder.py runs faster.

Run BEFORE people_finder.py (or while it's paused).

Run: python3 dedup_input.py
"""

import csv
import os

INPUT  = os.path.join('Sprint_Targets', 'Internships_Recomputed_Clean.csv')
OUTPUT = os.path.join('Sprint_Targets', 'Internships_Recomputed_Clean.csv')

with open(INPUT, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

before = len(rows)

# File is already sorted by Claude_Priority descending so first occurrence = best role
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

print(f"Removed {before - after} duplicate company rows. {after} remaining.")
print(f"Saved to: {OUTPUT}")
print(f"You can now restart people_finder.py — it will skip already-processed companies.")
