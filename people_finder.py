"""
people_finder.py — Finds LinkedIn contacts for top internship opportunities using Selenium.

For each role where both Parth_Priority AND Claude_Priority >= 50:
  - Google X-ray searches for Rose-Hulman alumni, GE Appliances alumni,
    campus recruiters, and team engineers
  - Extracts names + titles from snippets using Groq
  - Outputs Internship_References.csv with clickable =HYPERLINK() formulas

Setup:
    pip3 install selenium groq python-dotenv
    brew install --cask chromedriver

Run: python3 people_finder.py
"""

import csv
import os
import re
import time
import json
import random
from dotenv import load_dotenv
from groq import Groq

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

load_dotenv()

INPUT_CSV  = os.path.join('Sprint_Targets', 'Internships_Recomputed_Clean.csv')
OUTPUT_CSV = os.path.join('Sprint_Targets', 'Internship_References.csv')

DEBUG = False  # Set to True to see what Selenium is finding on each page

GROQ_REQUESTS   = 0
GROQ_LAST_RESET = time.time()
GROQ_LIMIT      = 28


def groq_wait():
    global GROQ_REQUESTS, GROQ_LAST_RESET
    now = time.time()
    if now - GROQ_LAST_RESET >= 60:
        GROQ_REQUESTS = 0
        GROQ_LAST_RESET = now
    if GROQ_REQUESTS >= GROQ_LIMIT:
        wait = 62 - (now - GROQ_LAST_RESET)
        print(f"  ⏳ Groq rate limit — waiting {wait:.0f}s...")
        time.sleep(max(wait, 1))
        GROQ_REQUESTS = 0
        GROQ_LAST_RESET = time.time()
    GROQ_REQUESTS += 1


def make_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def wait_for_captcha(driver):
    page = driver.page_source.lower()
    if 'unusual traffic' in page or 'captcha' in page or 'recaptcha' in page:
        print("\n  🚨 CAPTCHA detected! Please solve it in the Chrome window.")
        print("  Press ENTER here once you've solved it...")
        input()
        return True
    return False


def google_xray(driver, query, max_results=3, debug=False):
    from urllib.parse import quote
    search_url = f"https://www.google.com/search?q={quote(query)}&num=10"
    driver.get(search_url)
    time.sleep(random.uniform(2.5, 4.5))

    wait_for_captcha(driver)

    # Detect no-results / fallback results page
    page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    no_result_signals = [
        "no results found for",
        "showing results for",
        "did you mean:",
        "no results match",
        "your search did not match",
    ]
    for signal in no_result_signals:
        if signal in page_text:
            if debug:
                print(f"  [DEBUG] No real results (detected: \"{signal}\")")
            return []

    if debug:
        src = driver.page_source
        print(f"\n  [DEBUG] Page title: {driver.title}")
        print(f"  [DEBUG] Page source: {len(src)} chars")
        li_links = re.findall(r'href="(https://[^"]*linkedin\.com/in/[^"]*)"', src)
        print(f"  [DEBUG] LinkedIn hrefs in source: {len(li_links)}")
        for l in li_links[:5]:
            print(f"    {l}")

    results = []
    try:
        all_links = driver.find_elements(By.TAG_NAME, "a")
        for link_el in all_links:
            if len(results) >= max_results:
                break
            try:
                href = link_el.get_attribute("href") or ""
                if "linkedin.com/in/" not in href:
                    continue
                href = href.split("?")[0]  # strip tracking params

                # Walk up DOM to find nearest ancestor with useful snippet text
                snippet = ""
                el = link_el
                for _ in range(5):
                    try:
                        parent = el.find_element(By.XPATH, "..")
                        text = parent.text.strip()
                        if 20 < len(text) < 500:
                            snippet = text
                            break
                        el = parent
                    except Exception:
                        break

                if debug:
                    print(f"  [DEBUG] href: {href}")
                    print(f"  [DEBUG] snippet: {snippet[:120]!r}")

                if href and href not in [r[1] for r in results]:
                    results.append((snippet, href))

            except Exception:
                continue

    except Exception as e:
        print(f"  ⚠️  Parse error: {e}")

    if debug:
        print(f"  [DEBUG] Total extracted: {len(results)}")

    return results


def previously_at_ge(snippet):
    """
    Check if GE Appliances appears as a PAST employer in the snippet.
    LinkedIn snippets use · as separator, current employer comes first.
      "Wing · GE Appliances"  -> GE is past  ✅
      "GE Appliances · Wing"  -> GE is current ❌
    """
    s = snippet.lower()
    ge_idx = s.find("ge appliances")
    if ge_idx == -1:
        return False
    before_ge = s[:ge_idx]
    return "·" in before_ge or " at " in before_ge


def extract_person(client, snippet, linkedin_url, category=""):
    """Extract name + title from a Google snippet using Groq.
    For GE_Alumni, first checks snippet ordering to confirm GE is a past role."""
    if not snippet:
        return None

    # Fast string check before spending a Groq call
    if category == "GE_Alumni" and not previously_at_ge(snippet):
        return None

    groq_wait()
    prompt = f"""Extract the person's name and current job title from this LinkedIn Google snippet.

Snippet: {snippet}

Return ONLY valid JSON:
{{"name": "First Last", "title": "Job Title"}}

If unclear, return: {{"name": null, "title": null}}"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=60,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            name  = data.get('name')
            title = data.get('title')
            if name and title:
                label = f"{name} - {title}".replace('"', "'")
                url   = linkedin_url.replace('"', '%22')
                return f'=HYPERLINK("{url}","{label}")'
    except Exception:
        pass
    return None


def classify_company_name(client, company):
    """
    Use Groq to determine if the company name is ambiguous (also a common
    English word, surname, or noun). If ambiguous, we generate the anchor
    ourselves as "at CompanyName" — we don't ask Groq for the anchor since
    it hallucinates wrong industry context (e.g. "Wing airline").
    """
    groq_wait()
    prompt = f"""Is "{company}" an ambiguous company name that could also be a common English word, surname, or other noun unrelated to employment?

Examples of AMBIGUOUS names: Wing, Toast, Ramp, Stripe, Notion, Linear, Loom, Glean, Brex, Carta, Scale, Lever, Front, Arc
Examples of UNAMBIGUOUS names: Databricks, Anthropic, Robinhood, Snowflake, Palantir, ZoomInfo, Crowdstrike

Return ONLY valid JSON with no extra text:
{{"is_ambiguous": true}}
or
{{"is_ambiguous": false}}"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=20,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            is_ambiguous = json.loads(m.group(0)).get("is_ambiguous", False)
            anchor = f"at {company.strip()}" if is_ambiguous else ""
            return {"is_ambiguous": is_ambiguous, "anchor": anchor}
    except Exception:
        pass
    return {"is_ambiguous": False, "anchor": ""}


def build_queries(company, domain, is_ambiguous, anchor):
    co_term = f'"{anchor}"' if is_ambiguous and anchor else f'"{company}"'
    return {
        'Rose_Alumni':    f'site:linkedin.com/in {co_term} "Rose-Hulman"',
        'GE_Alumni':      f'site:linkedin.com/in {co_term} "GE Appliances"',
        'Recruiters':     f'site:linkedin.com/in {co_term} ("campus recruiter" OR "university recruiter" OR "emerging talent" OR "early careers")',
        'Team_Engineers': f'site:linkedin.com/in {co_term} "software engineer"',
    }


def extract_domain(client, role_title):
    groq_wait()
    prompt = f"""Extract 1-2 technical domain keywords from this internship role title for a LinkedIn search.
Role: {role_title}

Examples:
  "Backend Software Engineering Intern" -> "backend"
  "ML Platform Intern" -> "machine learning"
  "Embedded Systems Software Intern" -> "embedded systems"
  "Data Science Intern" -> "data science"
  "Agentic AI Tools Intern" -> "AI"

Return ONLY the keywords as a plain string."""

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=15,
        )
        return resp.choices[0].message.content.strip().strip('"').lower()
    except Exception:
        return "software engineer"


def clean_company(name):
    name = re.sub(r'[^\x00-\x7F]+', '', str(name))
    return name.strip()


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


_company_cache = {}


def process_role(driver, client, row):
    company = clean_company(row.get('Company', ''))
    role    = row.get('Role', '')

    print(f"  🔍 {company} — {role}")

    if company not in _company_cache:
        classification = classify_company_name(client, company)
        _company_cache[company] = classification
        flag = "⚠️  ambiguous" if classification['is_ambiguous'] else "✓ unambiguous"
        print(f"    Company: {flag} → anchor: '{classification['anchor']}'")
    else:
        classification = _company_cache[company]

    is_ambiguous = classification.get('is_ambiguous', False)
    anchor       = classification.get('anchor', '')
    domain       = extract_domain(client, role)
    queries      = build_queries(company, domain, is_ambiguous, anchor)

    result = {
        'Parth_Priority':  row.get('Parth_Priority', ''),
        'Claude_Priority': row.get('Claude_Priority', ''),
        'Company':         row.get('Company', ''),
        'Role':            role,
        'Location':        row.get('Location', ''),
        'Date_Posted':     row.get('Date_Posted', ''),
        'Apply_Link':      row.get('Apply_Link', ''),
    }

    for col, query in queries.items():
        raw_results = google_xray(driver, query, max_results=3, debug=DEBUG)
        links = []
        for snippet, url in raw_results:
            link = extract_person(client, snippet, url, category=col)
            if link:
                links.append(link)
        result[col] = ' | '.join(links) if links else ''
        print(f"    {col}: {len(links)} found")

    return result


def main():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("No GROQ_API_KEY in .env")
        return

    if not os.path.exists(INPUT_CSV):
        print(f"Could not find {INPUT_CSV}")
        return

    client = Groq(api_key=api_key)

    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))

    targets = [
        r for r in all_rows
        if safe_float(r.get('Parth_Priority'))  >= 30
        and safe_float(r.get('Claude_Priority')) >= 30
    ]

    print(f"\n📋 {len(all_rows)} total roles → {len(targets)} with both scores ≥ 50")

    already_done = set()
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                already_done.add((r.get('Company', ''), r.get('Role', '')))
        print(f"⏭️  Resuming — {len(already_done)} done, {len(targets) - len(already_done)} remaining")

    to_process = [
        r for r in targets
        if (r.get('Company', ''), r.get('Role', '')) not in already_done
    ]

    if not to_process:
        print("✅ All roles already processed.")
        return

    print(f"\n🌐 Opening Chrome... (solve any CAPTCHAs that appear)\n")
    driver = make_driver()

    output_fieldnames = [
        'Parth_Priority', 'Claude_Priority', 'Company', 'Role',
        'Location', 'Date_Posted', 'Apply_Link',
        'Rose_Alumni', 'GE_Alumni', 'Recruiters', 'Team_Engineers',
    ]

    file_mode = 'a' if already_done else 'w'

    try:
        with open(OUTPUT_CSV, file_mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=output_fieldnames, extrasaction='ignore')
            if not already_done:
                writer.writeheader()

            for i, row in enumerate(to_process):
                print(f"\n[{i+1}/{len(to_process)}]")
                result = process_role(driver, client, row)
                writer.writerow(result)
                f.flush()

    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted. Progress saved — rerun to continue.")
    finally:
        driver.quit()

    print(f"\n✅ Done. Saved to: {OUTPUT_CSV}")
    print("Open in Google Sheets via File > Import to see clickable links.")


if __name__ == "__main__":
    main()
