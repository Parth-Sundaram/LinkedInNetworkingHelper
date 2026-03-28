"""
message_gen.py — Generates personalized LinkedIn connection messages.

Run: python3 message_gen.py
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

CHAR_LIMIT = 300

YOUR_NAME    = "Parth Sundaram"
YOUR_SCHOOL  = "Rose-Hulman Institute of Technology"
YOUR_MAJOR   = "CS + Data Science"
YOUR_YEAR    = "junior"
YOUR_CLASS   = "Class of '27"
YOUR_CURRENT = "GE Appliances"
YOUR_PREV    = "Netra Systems (medical imaging software)"
YOUR_SKILLS  = "ML, software engineering, CUDA/GPU programming, full-stack"

TEMPLATES = {
    "rose_alumni": {
        "label": "Rose-Hulman Alum",
        "context_prompt": f"""Write a short LinkedIn connection note from a Rose-Hulman student to a Rose-Hulman alum who works at the target company.

Use this as your style reference — match the tone, warmth, and structure exactly:

---
Hey Mohit,
Hope you're doing well! I'm a CS/DS junior at Rose-Hulman (Class of '27) and saw you graduated from Rose in 2016 - I thought I'd reach out.

I'm really interested in the SWE Intern roles at Rivian for this summer. I'm currently at GE Appliances and have a good background in ML/Software Engineering.

Would you be comfortable with referring me? I'd also love to hear about your experience at Rivian, if you have a few minutes to chat.

Happy to send my resume or jump on a quick call. No pressure either way, I just wanted to connect with another Rose person.

Thanks,
Parth Sundaram
---

Key rules:
- Start with "Hey [name],"
- Mention their Rose grad year if provided, otherwise just reference the shared school
- Mention the specific role and company
- Reference current GE Appliances internship and relevant skills briefly
- Ask for a referral AND offer to chat — no pressure framing
- End with "Thanks, Parth Sundaram"
- Must be under {CHAR_LIMIT} characters — keep it tight, cut fluff""",
    },

    "ge_alumni": {
        "label": "GE Appliances Alum",
        "context_prompt": f"""Write a short LinkedIn connection note from a current GE Appliances intern to someone who previously worked at GE Appliances and now works at the target company.

Style reference — match this tone:
---
Hey [Name],
Hope you're doing well! I'm a CS/DS junior at Rose-Hulman (Class of '27) and currently interning at GE Appliances — I saw you worked there previously and thought I'd reach out.

I'm really interested in the [Role] at [Company] for this summer. Given your experience at both GE and [Company], I'd love to hear your perspective.

Would you be comfortable with referring me? Happy to send my resume or jump on a quick call. No pressure at all!

Thanks,
Parth Sundaram
---

Key rules:
- Start with "Hey [name],"
- Lead with the GE connection — it's the hook
- Mention the specific role
- Ask for referral with no-pressure framing
- End with "Thanks, Parth Sundaram"
- Must be under {CHAR_LIMIT} characters""",
    },

    "recruiter": {
        "label": "Campus/University Recruiter",
        "context_prompt": f"""Write a short LinkedIn connection note from a student to a campus recruiter at a company they just applied to.

Use these as style references — match the directness and brevity:

Example 1:
---
Hi Kendal! I just applied for the SWE Intern role at Capital One for Summer 2026. I'm a CS/DS junior at Rose-Hulman, currently at GE Appliances with experience in ML/data systems. Really interested in fintech infrastructure. Would love to connect!
---

Example 2:
---
Hi Pablo, thanks for connecting! I just applied for the SWE intern role at Stripe for this summer and wanted to reach out. I'm a junior at Rose-Hulman (CS/DS), previously worked at Netra Systems on medical imaging software, and I'm starting at GE Appliances next week. I made it to final rounds at Coinbase last cycle but didn't convert. Would you feel comfortable referring me? I'd be happy to send over my resume! No worries at all if you can't! Thanks, Parth Sundaram
---

Key rules:
- Start with "Hi [name]!"
- Say you just applied for the specific role
- Drop 1-2 relevant credentials (GE Appliances, Netra Systems, specific skills)
- Keep it punchy — recruiters are busy
- Ask to connect or for a referral, no-pressure ending
- Must be under {CHAR_LIMIT} characters""",
    },

    "engineer": {
        "label": "Team Engineer",
        "context_prompt": f"""Write a short LinkedIn connection note from a student to a software engineer who likely works on the team the student is applying to join.

Style reference:
---
Hi [Name], I just applied for the [Role] at [Company] and wanted to reach out to someone on the team. I'm a CS/DS junior at Rose-Hulman, currently at GE Appliances — I have relevant experience in [skill] and would love to hear what the team is actually working on. Would you be open to a quick chat? No worries if not — just wanted to connect!

Thanks, Parth Sundaram
---

Key rules:
- Start with "Hi [name],"
- Mention the specific role
- Show genuine curiosity about their team/work — engineers respond to this
- Reference 1 specific technical skill relevant to the role domain
- Keep it conversational, not formal
- Low-friction ask — quick chat OR just connect
- Must be under {CHAR_LIMIT} characters""",
    },
}


def generate_message(client, category, their_name, their_title, company, role,
                     their_grad_year="", extra_context=""):
    template = TEMPLATES[category]

    details = f"""Now write the actual message with these specific details:
- Their name: {their_name}
- Their title: {their_title}
- Their company: {company}
- Role applying for: {role}
- Your name: {YOUR_NAME} ({YOUR_SCHOOL}, {YOUR_MAJOR}, {YOUR_YEAR}, {YOUR_CLASS})
- Your current internship: {YOUR_CURRENT}
- Your previous internship: {YOUR_PREV}"""

    if their_grad_year:
        details += f"\n- Their Rose-Hulman grad year: {their_grad_year}"
    if extra_context:
        details += f"\n- Extra context: {extra_context}"

    details += f"\n\nWrite ONLY the message. No labels, no explanation. Under {CHAR_LIMIT} characters."

    prompt = template["context_prompt"] + "\n\n" + details

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250,
        )
        msg = resp.choices[0].message.content.strip()
        if len(msg) > CHAR_LIMIT:
            msg = msg[:CHAR_LIMIT].rsplit('.', 1)[0] + '.'
        return msg
    except Exception as e:
        return f"[Error: {e}]"


def copy_to_clipboard(text):
    try:
        import subprocess
        subprocess.run(['pbcopy'], input=text.encode(), check=True)
        print("✅ Copied to clipboard!")
    except Exception:
        print("⚠️  Could not copy. Select the text above manually.")


def get_category_choice():
    print("\nConnection type:")
    options = list(TEMPLATES.items())
    for i, (key, val) in enumerate(options, 1):
        print(f"  {i}. {val['label']}")
    while True:
        try:
            choice = int(input("Choose (1-4): ").strip())
            if 1 <= choice <= 4:
                return options[choice - 1][0]
        except ValueError:
            pass
        print("Enter 1-4.")


def main():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("No GROQ_API_KEY in .env")
        return

    client = Groq(api_key=api_key)

    print("\n" + "="*50)
    print("  LinkedIn Message Generator — Parth Sundaram")
    print("="*50)

    while True:
        try:
            category    = get_category_choice()
            their_name  = input("Their first name: ").strip()
            their_title = input("Their job title: ").strip()
            company     = input("Company: ").strip()
            role        = input("Role you're applying for: ").strip()

            grad_year = ""
            if category == "rose_alumni":
                grad_year = input("Their Rose grad year (press Enter to skip): ").strip()

            extra = input("Extra context? (press Enter to skip): ").strip()

            print("\n⏳ Generating...")
            msg = generate_message(client, category, their_name, their_title,
                                   company, role, grad_year, extra)

            while True:
                print("\n" + "─"*50)
                print(f"Message ({len(msg)}/300 chars):\n")
                print(msg)
                print("─"*50)

                action = input("\n[r] Regenerate  [c] Copy  [n] New person  [q] Quit: ").strip().lower()
                if action == 'r':
                    print("⏳ Regenerating...")
                    msg = generate_message(client, category, their_name, their_title,
                                           company, role, grad_year, extra)
                elif action == 'c':
                    copy_to_clipboard(msg)
                elif action == 'n':
                    break
                elif action == 'q':
                    print("\nDone.")
                    return

        except KeyboardInterrupt:
            print("\n\nDone.")
            return


if __name__ == "__main__":
    main()
