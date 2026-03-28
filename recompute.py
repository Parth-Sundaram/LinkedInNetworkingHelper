"""
recompute.py — Reads Internships_Scored_Recomputed.csv and outputs a clean version
with location tiers and both priority scores.

Run: python3 recompute.py
"""

import csv
import os

INPUT  = os.path.join('Sprint_Targets', 'Internships_Scored_Recomputed.csv')
OUTPUT = os.path.join('Sprint_Targets', 'Internships_Recomputed_Clean.csv')

CALIFORNIA_KEYWORDS = [
    'ca', 'california', 'san francisco', 'sf', 'san jose', 'los angeles', 'la',
    'santa clara', 'sunnyvale', 'mountain view', 'palo alto', 'menlo park',
    'redwood city', 'san diego', 'irvine', 'berkeley', 'oakland', 'san mateo',
    'culver city', 'santa monica', 'burbank', 'pasadena', 'fremont', 'pleasanton',
]
COASTAL_CITY_KEYWORDS = [
    'new york', 'nyc', 'brooklyn', 'manhattan',
    'boston', 'cambridge',
    'seattle', 'bellevue',
    'austin',
    'chicago',
    'washington', 'dc', 'arlington',
    'miami',
    'denver',
    'atlanta',
    'portland',
    'raleigh', 'durham',
    'philadelphia',
]
INTERNATIONAL_KEYWORDS = [
    'canada', 'toronto', 'vancouver', 'montreal',
    'uk', 'london', 'england',
    'india', 'bangalore', 'gurugram', 'hyderabad',
    'germany', 'berlin', 'munich',
    'france', 'paris',
    'australia', 'sydney', 'melbourne',
    'singapore', 'japan', 'tokyo',
    'netherlands', 'amsterdam',
    'ireland', 'dublin',
    'apac', 'emea', 'latam',
]

def get_location_tier(location):
    loc = str(location).lower()
    if any(k in loc for k in INTERNATIONAL_KEYWORDS):
        return 5, 0
    if any(k in loc for k in CALIFORNIA_KEYWORDS):
        return 1, 10
    if any(k in loc for k in COASTAL_CITY_KEYWORDS):
        return 2, 7
    if 'remote' in loc:
        return 4, 2
    return 3, 4

def safe_float(val, default=5.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def clean_company_name(name):
    """Remove emojis and special characters from company name"""
    import unicodedata
    if not name:
        return name
    # Remove emojis and control characters
    cleaned = ''.join(
        ch for ch in name 
        if unicodedata.category(ch)[0] not in ('C', 'So', 'Cn') 
        and not (0x1F300 <= ord(ch) <= 0x1F9FF)  # Emoji range
        and not (0x2600 <= ord(ch) <= 0x27BF)   # Miscellaneous symbols
    )
    return cleaned.strip()

def compute_parth_priority(recency, resume_match, cold_email, location_score):
    score = (
        (8/20) * recency +
        (5/20) * resume_match +
        (2/20) * cold_email +
        (5/20) * location_score
    )
    return round(score * 10, 1)

def compute_claude_priority(recency, resume_match, cold_email, location_score):
    score = (
        0.40 * resume_match +
        0.25 * recency +
        0.20 * location_score +
        0.15 * cold_email
    )
    return round(score * 10, 1)

def make_hyperlink(url, label="Apply"):
    if not url or url == 'Link not found':
        return ''
    url = url.replace('"', '%22')
    return f'=HYPERLINK("{url}","{label}")'

# Read input - skip title row
with open(INPUT, 'r', encoding='utf-8') as f:
    f.readline()  # Skip "Internships_Scored" title row
    reader = csv.DictReader(f)
    rows = list(reader)
    original_fieldnames = reader.fieldnames

print(f"Loaded {len(rows)} rows.")
print(f"Columns: {original_fieldnames[:5]}... (showing first 5)")

DROP_COLS = {'Alumni_Search', 'Recruiter_Search', 'Recomputed Priority', 'Competitiveness_Reason', 'Match_Reason', 'Cold_Email_Reason'}

output_rows = []
skipped_intl = 0

for row in rows:
    location = row.get('Location', '')
    tier, loc_score = get_location_tier(location)

    if tier == 5:
        skipped_intl += 1
        continue

    recency      = safe_float(row.get('Recency_Score'))
    resume_match = safe_float(row.get('Resume_Match_Score'))
    cold_email   = safe_float(row.get('Cold_Email_Score'))

    parth_score  = compute_parth_priority(recency, resume_match, cold_email, loc_score)
    claude_score = compute_claude_priority(recency, resume_match, cold_email, loc_score)

    new_row = {k: v for k, v in row.items() if k not in DROP_COLS}
    new_row['Company']         = clean_company_name(row.get('Company', ''))
    new_row['Apply_Link']      = make_hyperlink(row.get('Apply_Link', ''))
    new_row['Location_Tier']   = tier
    new_row['Parth_Priority']  = parth_score
    new_row['Claude_Priority'] = claude_score

    output_rows.append(new_row)

print(f"Removed {skipped_intl} international roles. {len(output_rows)} remaining.")

output_rows.sort(key=lambda x: float(x['Parth_Priority']), reverse=True)

# Build column order: priority columns first, then originals (minus dropped), other new cols at end
base_keys = [k for k in original_fieldnames if k not in DROP_COLS]
priority_keys = ['Parth_Priority', 'Claude_Priority', 'Location_Tier']

final_keys = priority_keys + base_keys

# Deduplicate preserving order
seen = set()
final_keys = [k for k in final_keys if not (k in seen or seen.add(k))]

with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=final_keys, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(output_rows)

print(f"Done. Saved to: {OUTPUT}")
print(f"\nLocation_Tier : 1=California  2=Coastal City  3=US  4=Remote")
print(f"Parth_Priority : 8/20 Recency + 5/20 Resume + 2/20 Cold Email + 5/20 Location (0-100)")
print(f"Claude_Priority: 40% Resume + 25% Recency + 20% Location + 15% Cold Email (0-100)")
print(f"\nOpen in Google Sheets via File > Import to get clickable Apply links.")
