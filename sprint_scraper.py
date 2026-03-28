import requests
import urllib.parse
import re
import os
import csv
from datetime import datetime, timedelta, date

# --- CONFIGURATION ---
GREENHOUSE_COMPANIES = [
    'databricks', 'scale', 'scaleai', 'affirm', 'brex', 'robinhood', 'stripe',
    'lyft', 'discord', 'plaid', 'cohere', 'anthropic', 'anduril', 'verkada',
    'duolingo', 'gusto', 'roblox', 'chime', 'datadog', 'nuro', 'typeface', 'meshy'
]
LEVER_COMPANIES = [
    'ramp', 'atlassian', 'figma', 'retool', 'canva', 'palantir', 'openai', 'snowflake'
]

LOCAL_MARKDOWN_FILE = 'SimplifyJobs.md'
OUTPUT_DIR = 'Sprint_Targets'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'Internships.csv')

# 1 = High Volume/Easiest, 4 = Elite/Hardest
DIFFICULTY_TIERS = {
    # Tier 1 - High volume, higher acceptance rates
    'amazon': 1, 'capital one': 1, 'state farm': 1, 'oracle': 1, 'mongodb': 1, 'salesforce': 1,
    'microsoft': 1, 'google': 1, 'meta': 1, 'apple': 1, 'ibm': 1, 'intel': 1, 'qualcomm': 1,
    'nvidia': 1, 'cisco': 1, 'vmware': 1, 'paypal': 1, 'ebay': 1, 'linkedin': 1,
    'uber': 1, 'doordash': 1, 'airbnb': 1, 'dropbox': 1, 'bloomberg': 1, 'expedia': 1,
    'booking': 1, 'yelp': 1, 'zillow': 1, 'wayfair': 1, 'chewy': 1, 'toast': 1,
    'hubspot': 1, 'zendesk': 1, 'twilio': 1, 'workday': 1, 'intuit': 1, 'veeva': 1,
    # Tier 2 - Competitive but approachable
    'databricks': 2, 'datadog': 2, 'servicenow': 2, 'adobe': 2, 'atlassian': 2,
    'rivian': 2, 'okta': 2, 'cloudflare': 2, 'hashicorp': 2, 'confluent': 2,
    'crowdstrike': 2, 'elastic': 2, 'gitlab': 2, 'github': 2, 'snowflake': 2,
    'splunk': 2, 'pagerduty': 2, 'newrelic': 2, 'dynatrace': 2, 'lyft': 2,
    # Tier 3 - Selective, strong brand, fewer spots
    'ramp': 3, 'brex': 3, 'plaid': 3, 'affirm': 3, 'chime': 3, 'robinhood': 3,
    'discord': 3, 'duolingo': 3, 'roblox': 3, 'gusto': 3, 'notion': 3, 'airtable': 3,
    'canva': 3, 'retool': 3, 'vercel': 3, 'rippling': 3, 'carta': 3, 'glean': 3,
    'verkada': 3, 'samsara': 3, 'vanta': 3, 'loom': 3, 'figma': 3,
    # Tier 4 - Elite, extremely competitive
    'scale': 4, 'scaleai': 4, 'openai': 4, 'neuralink': 4, 'nuro': 4, 'waymo': 4,
    'stripe': 4, 'palantir': 4, 'anthropic': 4, 'cohere': 4, 'anduril': 4,
    'jane street': 4, 'citadel': 4, 'two sigma': 4, 'hudson river': 4, 'drw': 4,
    'de shaw': 4, 'renaissance': 4, 'spacex': 4, 'tesla': 4, 'deepmind': 4,
    'mistral': 4, 'perplexity': 4,
}

def normalize_company(name):
    """Strip punctuation, spaces, and common corporate suffixes for fuzzy matching."""
    name = str(name).lower()
    # Remove common corporate suffixes first (order matters — longest first)
    suffixes = [
        ' technologies', ' technology', ' solutions', ' software', ' systems',
        ' platforms', ' holdings', ' group', ' labs', ' lab', ' ai',
        ' inc.', ' inc', ' corp.', ' corp', ' llc', ' ltd', ' co.', ' co', ' hq',
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Remove all non-alphanumeric characters
    name = re.sub(r'[^a-z0-9]', '', name)
    return name.strip()

# Pre-normalize the tier keys once at startup for efficiency
_NORMALIZED_TIERS = {normalize_company(k): v for k, v in DIFFICULTY_TIERS.items()}

def get_difficulty_tier(company):
    normalized = normalize_company(company)
    # 1. Exact match
    if normalized in _NORMALIZED_TIERS:
        return _NORMALIZED_TIERS[normalized]
    # 2. Substring match — catches "googlecloud" -> "google", "scaleai" -> "scale"
    for key, tier in _NORMALIZED_TIERS.items():
        if key and (key in normalized or normalized in key):
            return tier
    return 3  # Default

def age_to_date(age_str):
    """Converts '0d', '3d', '14d' etc. from the Simplify README into a YYYY-MM-DD date string."""
    age_str = re.sub(r'<[^>]+>', '', age_str).strip()
    match = re.match(r'(\d+)d', age_str)
    if match:
        days_ago = int(match.group(1))
        return (date.today() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    return ''

def generate_xray_link(company, search_type):
    if search_type == "alumni":
        query = f'site:linkedin.com/in "{company}" "Rose-Hulman"'
    elif search_type == "recruiter":
        query = f'site:linkedin.com/in "{company}" ("University Recruiter" OR "Technical Recruiter")'
    else:
        return ""
    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"

def is_valid_role(title, location):

    if '🎓' in str(title): return False
    title_lower = str(title).lower()
    loc_lower = str(location).lower()

    if not re.search(r'\b(intern|internship|summer)\b', title_lower): return False
    if not re.search(r'\b(software|swe|machine learning|ml|data|backend|frontend|ai|embedded|firmware|hardware)\b', title_lower): return False
    if re.search(r'\b(senior|phd|master|M\.S\.|staff|manager|director|lead|principal|new grad|internal|internals)\b', title_lower): return False

    intl_keywords = ['serbia', 'netherlands', 'denmark', 'poland', 'spain', 'uk', 'london',
                     'india', 'gurugram', 'canada', 'toronto', 'vancouver', 'paris',
                     'berlin', 'sydney', 'apac', 'emea']
    if any(k in loc_lower for k in intl_keywords): return False

    return True

def clean_markdown_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()

def scrape_apis():
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

    for company in GREENHOUSE_COMPANIES:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                for job in resp.json().get('jobs', []):
                    loc = job.get('location', {}).get('name', 'N/A')
                    if is_valid_role(job.get('title', ''), loc):
                        results.append({
                            'Company': company.capitalize(), 'Role': job.get('title'), 'Location': loc,
                            'Apply_Link': job.get('absolute_url'), 'Date_Posted': '',
                            'Difficulty_Tier': get_difficulty_tier(company)
                        })
        except: pass

    for company in LEVER_COMPANIES:
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                for job in resp.json():
                    loc = job.get('categories', {}).get('location', 'N/A')
                    if is_valid_role(job.get('text', ''), loc):
                        results.append({
                            'Company': company.capitalize(), 'Role': job.get('text'), 'Location': loc,
                            'Apply_Link': job.get('hostedUrl'), 'Date_Posted': '',
                            'Difficulty_Tier': get_difficulty_tier(company)
                        })
        except: pass

    return results

def parse_local_markdown():
    """Reads the HTML tables inside the SimplifyJobs.md and extracts matching roles."""
    results = []
    if not os.path.exists(LOCAL_MARKDOWN_FILE):
        print(f"⚠️ Could not find '{LOCAL_MARKDOWN_FILE}'. Skipping local parse.")
        return results

    print(f"📄 Parsing local file: {LOCAL_MARKDOWN_FILE}...")

    with open(LOCAL_MARKDOWN_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    rows = re.findall(r'<tr>(.*?)</tr>', content, re.DOTALL)
    last_company = "Unknown Company"

    for row in rows:
        tds = re.findall(r'<td>(.*?)</td>', row, re.DOTALL)

        if len(tds) >= 4:
            raw_company = re.sub(r'<[^>]+>', '', tds[0]).strip()
            if raw_company == '↳':
                company = last_company
            else:
                company = raw_company
                last_company = company

            role = re.sub(r'<[^>]+>', '', tds[1]).strip()
            location = re.sub(r'<br\s*/?>', ' | ', tds[2])
            location = re.sub(r'<[^>]+>', '', location).strip()

            link_match = re.search(r'href="([^"]+)"', tds[3])
            link = link_match.group(1) if link_match else "Link not found"

            # 5. Parse posting date from Age column (5th td: "0d", "3d", etc.)
            date_posted = age_to_date(tds[4]) if len(tds) >= 5 else ''

            if is_valid_role(role, location):
                results.append({
                    'Company': company,
                    'Role': role,
                    'Location': location,
                    'Apply_Link': link,
                    'Date_Posted': date_posted,
                    'Difficulty_Tier': get_difficulty_tier(company)
                })

    return results

if __name__ == "__main__":
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Executing Sprint Scraper...")

    all_jobs = scrape_apis() + parse_local_markdown()

    # Deduplicate by apply link
    unique_jobs_dict = {job['Apply_Link']: job for job in all_jobs}
    unique_jobs = list(unique_jobs_dict.values())

    if not unique_jobs:
        print("No matches found. Ensure SimplifyJobs.md is in the folder.")
    else:
        unique_jobs.sort(key=lambda x: x['Difficulty_Tier'])

        for job in unique_jobs:
            job['Alumni_Search'] = generate_xray_link(job['Company'], "alumni")
            job['Recruiter_Search'] = generate_xray_link(job['Company'], "recruiter")

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        keys = ['Difficulty_Tier', 'Company', 'Role', 'Location', 'Date_Posted', 'Apply_Link', 'Alumni_Search', 'Recruiter_Search']
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(unique_jobs)

        # Print a quick breakdown of how many roles landed in each tier
        from collections import Counter
        tier_counts = Counter(job['Difficulty_Tier'] for job in unique_jobs)
        print(f"✅ Success! Extracted {len(unique_jobs)} US-based roles.")
        for tier in sorted(tier_counts):
            print(f"   Tier {tier}: {tier_counts[tier]} roles")
        print(f"📂 Saved to: {OUTPUT_FILE}")
        print("Sort order: Tier 1 (Highest Probability) -> Tier 4 (Most Competitive).")
