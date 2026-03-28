import csv
import os

FILE = os.path.join('Sprint_Targets', 'Internships_Scored.csv')

INT_COLS = ['Priority_Score', 'Competitiveness_Score', 'Resume_Match_Score',
            'Cold_Email_Score', 'Recency_Score', 'Difficulty_Tier']

with open(FILE, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

for row in rows:
    for col in INT_COLS:
        val = row.get(col)
        if val and str(val).strip().lstrip('-').isdigit():
            row[col] = int(str(val).strip())

with open(FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Done.")
