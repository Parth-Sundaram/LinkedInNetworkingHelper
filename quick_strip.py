import csv
import os
import re

INPUT  = os.path.join('Sprint_Targets', 'Internships_Scored.csv')
OUTPUT = os.path.join('Sprint_Targets', 'Internships_Scored.csv')

with open(INPUT, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

def should_exclude(role):
    r = role.strip()
    r_lower = r.lower()
    if '🎓' in r: return True
    if re.search(r'\b(grad|graduate|unpaid|ms|m\.s\.)\b', r_lower): return True
    if re.search(r'\bproduct\b', r_lower): return True
    return False

before = len(rows)
rows = [r for r in rows if not should_exclude(r.get('Role', ''))]
after = len(rows)

with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Removed {before - after} roles. {after} remaining.")
