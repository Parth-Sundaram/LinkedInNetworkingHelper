"""
scorer.py — Evaluates internship opportunities against your resume using Groq.

Setup:
    1. pip install groq python-dotenv
    2. Create a .env file in this folder with: GROQ_API_KEY=your_key_here
    3. Place your Internships.csv in the Sprint_Targets/ folder
    4. Run: python scorer.py

Output:
    Sprint_Targets/Internships_Scored.csv
"""

import re
import os
import csv
import json
import time
from datetime import datetime, date
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# --- CONFIGURATION ---
INPUT_CSV  = os.path.join('Sprint_Targets', 'Internships.csv')
OUTPUT_DIR = 'Sprint_Targets'
OUTPUT_CSV = os.path.join(OUTPUT_DIR, 'Internships_Scored.csv')

RESUME = """
PARTH SUNDARAM — CS + Data Science, Rose-Hulman Institute of Technology (Sep 2023 – May 2027)

EXPERIENCE:
- Software Engineer Intern, Netra Systems (Jun–Sep 2025): Medical imaging app used by Genentech/Johns Hopkins.
  Multithreading, GPU programming (CUDA), MFC GUI, embedded firmware, image processing pipelines.
- Software Engineer Intern, GE Appliances (Current): actively working here now.
- Software Engineer Intern, GE Appliances (Current, 2026): embedded software and appliance firmware.
- Tutor, AskRose (Nov 2023 – Nov 2025): Math and science tutoring.

PROJECTS:
- Algorithmic Stock Trading System (Python, PyTorch, NLP) — backtesting, ML price prediction, sentiment analysis, portfolio optimization
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

EXTRACURRICULARS: President of South Asian Students Association, Competitive Programming Team, Dean's List
"""

SYSTEM_PROMPT = f"""You are an internship application strategist. You will be given a job listing
and a student resume, and you must return ONLY a valid JSON object — no explanation, no markdown.

The student's resume:
{RESUME}

Return ONLY a valid JSON object. No explanation, no markdown, no text before or after.
All string values MUST be in double quotes. Correct format example:
{{
  "company_competitiveness": 7,
  "resume_match": 6,
  "cold_email_viability": 5,
  "competitiveness_reason": "One sentence about how hard it is to get in.",
  "match_reason": "One sentence about how well the resume fits.",
  "cold_email_reason": "One sentence about whether cold emailing would help."
}}
Scores: company_competitiveness 1=very easy 10=extremely selective. resume_match 1=poor fit 10=perfect. cold_email_viability 1=pointless 10=highly effective."""

def compute_recency_score(date_posted_str):
    """Returns 1-10. 10 = posted today, decays to 1 after 30+ days. Returns 5 if date unknown."""
    if not date_posted_str or date_posted_str.strip() in ('', 'N/A', 'Unknown'):
        return 5
    try:
        posted = datetime.strptime(date_posted_str.strip(), '%Y-%m-%d').date()
        days_ago = (date.today() - posted).days
        if days_ago <= 1:   return 10
        if days_ago <= 3:   return 9
        if days_ago <= 7:   return 8
        if days_ago <= 14:  return 6
        if days_ago <= 21:  return 4
        if days_ago <= 30:  return 2
        return 1
    except ValueError:
        return 5

def compute_priority_score(comp, recency, match, cold_email):
    """
    Weighted average matching Parth's priority ranking:
      Company competitiveness (inverted) 30%  — lower comp score = better opportunity
      Recency                            25%
      Resume match                       30%
      Cold email viability               15%
    """
    # Invert competitiveness: a tier-1 easy company scores 10, elite scores 1
    comp_inverted = 11 - comp
    raw = (comp_inverted * 0.30) + (recency * 0.25) + (match * 0.30) + (cold_email * 0.15)
    # Scale to 0-100
    return round((raw / 10) * 100)

def score_to_action(priority_score):
    if priority_score >= 70: return "Apply This Week"
    if priority_score >= 45: return "Apply Soon"
    return "Low Priority"

def extract_fields(raw):
    """Robustly extract fields from potentially malformed JSON by parsing each field individually."""
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
    prompt = SYSTEM_PROMPT + f"\n\nCompany: {company}\nRole: {role}\nLocation: {location}"
    for attempt in range(3):
        try:
            response = client.generate_content(prompt)
            raw = response.text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            return extract_fields(raw)
        except Exception as e:
            err_str = str(e)
            print(f"  ⚠️  API error on attempt {attempt+1}: {e}")
            # Handle Gemini quota errors
            wait_match = re.search(r'retry_delay.*?(\d+)', err_str)
            if '429' in err_str or 'quota' in err_str.lower():
                wait_secs = int(wait_match.group(1)) if wait_match else 60
                print(f"  ⏳ Rate limit — waiting {wait_secs}s...")
                time.sleep(wait_secs)
            else:
                time.sleep(3)
    return None

def load_already_scored():
    """Returns a set of Apply_Links that are already scored in the output CSV."""
    scored = set()
    if not os.path.exists(OUTPUT_CSV):
        return scored
    with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            # Only count rows that actually have a score, not failed ones
            if row.get('Priority_Score', '').strip():
                scored.add(row.get('Apply_Link', '').strip())
    return scored

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ No GEMINI_API_KEY found. Add GEMINI_API_KEY=your_key to your .env file")
        return

    genai.configure(api_key=api_key)
    client = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"temperature": 0.2}
    )

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

    # --- CHECKPOINTING ---
    already_scored = load_already_scored()
    is_resume = len(already_scored) > 0
    rows_to_score = [r for r in rows if r.get('Apply_Link', '').strip() not in already_scored]

    print(f"\n📋 Loaded {len(rows)} total roles from {INPUT_CSV}")
    if is_resume:
        print(f"⏭️  Resuming — {len(already_scored)} already scored, {len(rows_to_score)} remaining")
    print(f"🤖 Scoring with Gemini (gemini-1.5-flash)...")
    print(f"📝 Appending results live to {OUTPUT_CSV}\n")

    # Open in append mode if resuming, write mode if fresh start
    file_mode = 'a' if is_resume else 'w'

    results = []
    with open(OUTPUT_CSV, file_mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=available_keys, extrasaction='ignore')
        if not is_resume:
            writer.writeheader()

        for i, row in enumerate(rows_to_score):
            company    = row.get('Company', 'Unknown')
            role       = row.get('Role', 'Unknown')
            location   = row.get('Location', 'N/A')
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

            time.sleep(1.0)

    total_done = len(already_scored) + len(results)
    print(f"\n✅ Session complete! Scored {len(results)} new roles ({total_done}/{len(rows)} total).")
    print(f"📂 Saved to: {OUTPUT_CSV}")

    if total_done < len(rows):
        print(f"⏸️  {len(rows) - total_done} roles remaining — run again tomorrow to continue.")

    actions = [r['Action'] for r in results]
    print(f"\n📊 This session:")
    for label in ["Apply This Week", "Apply Soon", "Low Priority", "Score Failed"]:
        print(f"   {label}: {actions.count(label)}")
    print("\nNote: CSV is in arrival order. Sort by Priority_Score descending in Excel/Sheets.")

if __name__ == "__main__":
    main()
