"""
scorer_claude.py — Evaluates internship opportunities against your resume using Claude Haiku.

Setup:
    1. pip3 install anthropic python-dotenv
    2. Add to .env file: ANTHROPIC_API_KEY=your_key_here
    3. Place Internships.csv in Sprint_Targets/ folder
    4. Run: python3 scorer_claude.py

Cost estimate: ~$0.87 for 700 rows with Claude Haiku 4.5
Output: Sprint_Targets/Internships_Scored.csv
"""

import re
import os
import csv
import json
import time
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import anthropic

load_dotenv()

# --- CONFIGURATION ---
INPUT_CSV  = os.path.join('Sprint_Targets', 'Internships.csv')
OUTPUT_DIR = 'Sprint_Targets'
OUTPUT_CSV = os.path.join(OUTPUT_DIR, 'Internships_Scored_Claude.csv')

RESUME = """
PARTH SUNDARAM — CS + Data Science, Rose-Hulman Institute of Technology (Sep 2023 – May 2027)

EXPERIENCE:
- Software Engineer Intern, GE Appliances (Current, 2026): embedded software and appliance firmware.
- Software Engineer Intern, Netra Systems (Jun–Sep 2025): Medical imaging app used by Genentech/Johns Hopkins.
  Multithreading, GPU programming (CUDA), MFC GUI, embedded firmware, image processing pipelines.
- Tutor, AskRose (Nov 2023 – Nov 2025): Math and science tutoring.

PROJECTS:
- Algorithmic Stock Trading System (Python, PyTorch, NLP) — backtesting, ML price prediction, sentiment analysis
- RL Clue Agent (Python, PyTorch) — deep Q-learning, policy gradients, Bayesian inference, epsilon decay
- Club Management Web App (React, SQL, Firebase) — full-stack, auth, real-time, 100+ concurrent users
- Heart Disease Prediction (Python, Scikit-learn, R) — Random Forest, XGBoost, feature engineering
- Grocery Mobile App (React Native, SQLite, Firebase) — barcode scanning, predictive algorithms
- Genetic Algorithm Simulator (Java) — fitness functions, mutation operators, convergence analysis

SKILLS:
- Languages: Python, Java, C++, C, SQL, R, JavaScript, HTML/CSS
- ML/AI: PyTorch, TensorFlow, Scikit-learn, Pandas, NumPy
- Tech: CUDA, Git, Linux, Firebase, React, SQLite, Arduino
- Concepts: Deep Learning, RL, NLP, Computer Vision, Algorithm Design

SCHOOL: Rose-Hulman Institute of Technology — strong engineering school, not a target school for FAANG
EXTRACURRICULARS: President of South Asian Students Association, Competitive Programming Team, Dean's List
"""

SYSTEM_PROMPT = f"""You are a brutally honest internship application strategist operating in early 2026.

MARKET CONTEXT — FACTOR THIS INTO EVERY SCORE:
- The 2025-2026 tech intern market is one of the worst in a decade
- Major layoffs at Meta, Google, Amazon, Microsoft, and others in 2024-2025 flooded the market with experienced candidates competing directly with interns
- Top schools (MIT, Stanford, CMU, Berkeley) produce thousands of applicants per role who have priority at FAANG
- Rose-Hulman is a respected engineering school but is NOT a target/feeder school for top-tier tech companies
- Average SWE intern application gets 500-2000+ applicants at tier 1-2 companies in this market
- Many companies have cut intern headcount 30-50% vs 2022-2023 peaks
- This student has 1 real internship (small medical imaging company) and side projects — competitive for mid-tier, long shot at elite

SCORING RULES — USE THE FULL RANGE, BE SPECIFIC AND HARSH:

company_competitiveness (1-10): How hard is this specific role to get in 2026?
  1-3 = Small startups, non-tech companies, regional orgs — low applicant volume
  4-5 = Mid-size tech, decent brand, hundreds of applicants but realistic
  6-7 = Well-known tech (Cisco, Oracle, Twilio, Salesforce) — strong competition
  8-9 = Top-tier (Google, Meta, Amazon, Microsoft, NVIDIA, Apple) — elite bar, thousands of applicants
  10  = OpenAI, Anthropic, Citadel, Jane Street — near-impossible without referral/exceptional pedigree

resume_match (1-10): How well does THIS student's background match THIS specific role?
  Be specific about gaps. Do NOT give 7+ unless there is direct relevant experience.
  1-3 = Wrong domain, missing core skills
  4-5 = Some overlap but significant gaps
  6-7 = Decent fit, most skills present, minor gaps
  8-9 = Strong direct match, relevant experience
  10  = Perfect fit (rare)

cold_email_viability (1-10): Will a cold email realistically help at this company?
  1-3 = Large company with formal ATS pipelines, cold email ignored
  4-6 = Mid-size, small chance, worth trying
  7-10 = Startup or small company where email reaches hiring manager directly
  IMPORTANT: Ignore the student's current employer when scoring this. Only consider company size/culture.

The student's resume:
{RESUME}

Return ONLY a valid JSON object. No explanation, no markdown, no text before or after.
{{
  "company_competitiveness": 7,
  "resume_match": 5,
  "cold_email_viability": 3,
  "competitiveness_reason": "One honest sentence about difficulty in the 2026 market for this specific role.",
  "match_reason": "One specific sentence naming actual skill gaps or strengths.",
  "cold_email_reason": "One sentence about whether cold email realistically helps here."
}}"""


def compute_recency_score(date_posted_str):
    if not date_posted_str or date_posted_str.strip() in ('', 'N/A', 'Unknown'):
        return 5
    try:
        posted = datetime.strptime(date_posted_str.strip(), '%Y-%m-%d').date()
        days_ago = (date.today() - posted).days
        if days_ago <= 1:  return 10
        if days_ago <= 3:  return 9
        if days_ago <= 7:  return 8
        if days_ago <= 14: return 6
        if days_ago <= 21: return 4
        if days_ago <= 30: return 2
        return 1
    except ValueError:
        return 5


def compute_priority_score(comp, recency, match, cold_email):
    comp_inverted = 11 - comp
    raw = (comp_inverted * 0.30) + (recency * 0.25) + (match * 0.30) + (cold_email * 0.15)
    return round((raw / 10) * 100)


def score_to_action(priority_score):
    if priority_score >= 70: return "Apply This Week"
    if priority_score >= 45: return "Apply Soon"
    return "Low Priority"


def extract_fields(raw):
    result = {}
    for key in ('company_competitiveness', 'resume_match', 'cold_email_viability'):
        m = re.search(rf'"{key}"\s*:\s*(\d+)', raw)
        if m:
            result[key] = int(m.group(1))
    for key in ('competitiveness_reason', 'match_reason', 'cold_email_reason'):
        m = re.search(rf'"{key}"\s*:\s*"*([^"{{}}]+)"*', raw)
        if m:
            result[key] = m.group(1).strip().strip('"').strip()
    return result if len(result) == 6 else None


def evaluate_role(client, company, role, location):
    prompt = f"Company: {company}\nRole: {role}\nLocation: {location}"
    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                temperature=0.2,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            result = extract_fields(raw)
            if result:
                return result
            print(f"  ⚠️  Parse failed on attempt {attempt+1} for {company} — {role}")
            print(f"       Raw: {raw[:200]}")
            time.sleep(1)
        except anthropic.RateLimitError:
            print(f"  ⏳ Rate limit hit — waiting 65s...")
            time.sleep(65)
        except Exception as e:
            print(f"  ⚠️  API error on attempt {attempt+1}: {e}")
            time.sleep(3)
    return None


def load_already_scored():
    scored = set()
    if not os.path.exists(OUTPUT_CSV):
        return scored
    with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('Priority_Score', '').strip():
                scored.add(row.get('Apply_Link', '').strip())
    return scored


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No ANTHROPIC_API_KEY found. Add ANTHROPIC_API_KEY=your_key to your .env file")
        return

    client = anthropic.Anthropic(api_key=api_key)

    if not os.path.exists(INPUT_CSV):
        print(f"❌ Could not find {INPUT_CSV}. Run scraper.py first.")
        return

    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    output_keys = [
        'Priority_Score', 'Action', 'Difficulty_Tier', 'Company', 'Role', 'Location',
        'Competitiveness_Score', 'Resume_Match_Score', 'Cold_Email_Score', 'Recency_Score',
        'Competitiveness_Reason', 'Match_Reason', 'Cold_Email_Reason',
        'Apply_Link', 'Alumni_Search', 'Recruiter_Search', 'Date_Posted',
    ]
    base_keys = list(rows[0].keys()) if rows else []
    score_keys = ['Priority_Score', 'Action', 'Competitiveness_Score', 'Resume_Match_Score',
                  'Cold_Email_Score', 'Recency_Score', 'Competitiveness_Reason', 'Match_Reason', 'Cold_Email_Reason']
    available_keys = [k for k in output_keys if k in base_keys + score_keys]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    already_scored = load_already_scored()
    is_resume = len(already_scored) > 0
    rows_to_score = [r for r in rows if r.get('Apply_Link', '').strip() not in already_scored]

    print(f"\n📋 Loaded {len(rows)} total roles from {INPUT_CSV}")
    if is_resume:
        print(f"⏭️  Resuming — {len(already_scored)} already scored, {len(rows_to_score)} remaining")
    print(f"🤖 Scoring with Claude Haiku 4.5...")
    print(f"💰 Using free tier — 5 req/min, estimated time: {len(rows_to_score) * 12.5 / 60:.0f} minutes")
    print(f"📝 Writing results live to {OUTPUT_CSV}\n")

    file_mode = 'a' if is_resume else 'w'
    results = []

    with open(OUTPUT_CSV, file_mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=available_keys, extrasaction='ignore')
        if not is_resume:
            writer.writeheader()

        for i, row in enumerate(rows_to_score):
            company     = row.get('Company', 'Unknown')
            role        = row.get('Role', 'Unknown')
            location    = row.get('Location', 'N/A')
            date_posted = row.get('Date_Posted', '')

            print(f"[{i+1}/{len(rows_to_score)}] {company} — {role}")

            scores = evaluate_role(client, company, role, location)

            if scores:
                recency  = compute_recency_score(date_posted)
                priority = compute_priority_score(
                    scores['company_competitiveness'],
                    recency,
                    scores['resume_match'],
                    scores['cold_email_viability']
                )
                action = score_to_action(priority)
                result = {
                    **row,
                    'Priority_Score':         priority,
                    'Action':                 action,
                    'Competitiveness_Score':  scores['company_competitiveness'],
                    'Resume_Match_Score':     scores['resume_match'],
                    'Cold_Email_Score':       scores['cold_email_viability'],
                    'Recency_Score':          recency,
                    'Competitiveness_Reason': scores.get('competitiveness_reason', ''),
                    'Match_Reason':           scores.get('match_reason', ''),
                    'Cold_Email_Reason':      scores.get('cold_email_reason', ''),
                }
            else:
                result = {
                    **row,
                    'Priority_Score': '', 'Action': 'Score Failed',
                    'Competitiveness_Score': '', 'Resume_Match_Score': '',
                    'Cold_Email_Score': '',      'Recency_Score': '',
                    'Competitiveness_Reason': '', 'Match_Reason': '', 'Cold_Email_Reason': '',
                }

            writer.writerow(result)
            f.flush()
            results.append(result)
            time.sleep(12.5)

    total_done = len(already_scored) + len(results)
    print(f"\n✅ Session complete! Scored {len(results)} new roles ({total_done}/{len(rows)} total).")
    print(f"📂 Saved to: {OUTPUT_CSV}")

    actions = [r['Action'] for r in results]
    print(f"\n📊 This session:")
    for label in ["Apply This Week", "Apply Soon", "Low Priority", "Score Failed"]:
        print(f"   {label}: {actions.count(label)}")
    print("\nSort by Priority_Score descending in Excel/Sheets.")


if __name__ == "__main__":
    main()
