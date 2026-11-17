"""OpenRouter API client for AI content generation using free models.

Usage:
    from app.openrouter import generate_blog_article, generate_company_guide

Environment:
    OPENROUTER_API_KEY — required for production use
    OPENROUTER_MODEL   — optional, defaults to free tier models
"""
import os
import textwrap
from typing import Optional

import requests

# Free-tier models on OpenRouter (verified as of 2026-11)
# These models cost $0 per token. Rate limits apply.
DEFAULT_FREE_MODELS = [
    "google/gemma-4-31b-it:free",      # Google Gemma 4 31B — strong instruction following
    "google/gemma-4-26b-a4b-it:free",  # Google Gemma 4 26B MoE — good reasoning
    "nvidia/nemotron-3.5-lightning:free",  # NVIDIA — fast, good for summaries
    "inclusionai/ling-3.2-flash:free",  # Fast hybrid reasoning
]

DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", DEFAULT_FREE_MODELS[0])
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. Get a free key at https://openrouter.ai/keys"
        )
    return key


def _call(messages: list, model: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2000) -> str:
    """Call OpenRouter chat completions with retry fallback across free models."""
    key = _api_key()
    models = [model] if model else DEFAULT_FREE_MODELS
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("SITE_URL", "https://jobboard.example.com"),
        "X-Title": "Fortune 500 Job Board Content Generator",
    }
    payload = {
        "model": None,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for m in models:
        payload["model"] = m
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"]
            if "error" in data:
                last_error = f"{m}: {data['error']}"
                continue
        except Exception as e:
            last_error = f"{m}: {e}"
            continue

    raise RuntimeError(f"All OpenRouter models failed. Last error: {last_error}")


# ═══════════════════════════════════════════════════════════════════
#  CONTENT GENERATION PROMPTS
# ═══════════════════════════════════════════════════════════════════

def generate_blog_article(company_name: str, job_titles: list, ats: str, job_count: int) -> str:
    """Generate a blog article about a company based on their live job data."""
    titles_sample = ", ".join(job_titles[:8]) if job_titles else "various roles"
    prompt = f"""Write a comprehensive, SEO-friendly blog article about careers at {company_name}.

Context:
- {company_name} is currently hiring for {job_count} open roles via their {ats} ATS board.
- Some of their active roles include: {titles_sample}.
- The article should help job seekers understand what {company_name} looks for, how their interview process works, and how to stand out.

Requirements:
1. Write 800-1200 words in a professional, helpful tone
2. Include these sections: Introduction, What {company_name} Looks For, The Interview Process, High-Volume Roles, Application Tips, and Conclusion
3. Mention that the data comes from their official {ats} board and that readers can apply directly
4. Include a call-to-action encouraging readers to browse live openings
5. Make it informative and actionable — not generic fluff
6. Format as clean HTML with <h2> and <p> tags (no <html> or <body> wrappers)
7. Include one relevant blockquote with a pro tip

Output only the HTML article content."""

    return _call(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.75,
        max_tokens=2500,
    )


def generate_company_meta_description(company_name: str, job_count: int, top_roles: list) -> str:
    """Generate an SEO meta description for a company page."""
    roles = ", ".join(top_roles[:4]) if top_roles else "engineering, product, design"
    prompt = f"""Write a concise, compelling SEO meta description (under 160 characters) for a job board page about {company_name} careers.

Details:
- {company_name} has {job_count} live openings
- Top roles: {roles}
- Every listing links directly to {company_name}'s official ATS board
- No aggregators, no dead listings

Output only the meta description text — no quotes, no HTML."""

    result = _call(messages=[{"role": "user", "content": prompt}], temperature=0.5, max_tokens=100)
    return result.strip().strip('"').strip("'")[:160]


def generate_role_guide(role_title: str, companies_hiring: list, total_openings: int) -> str:
    """Generate a guide article for a specific role type."""
    companies = ", ".join(companies_hiring[:6]) if companies_hiring else "top tech companies"
    prompt = f"""Write a comprehensive career guide for the role: {role_title}.

Context:
- There are currently {total_openings} open {role_title} positions at companies like {companies}.
- These jobs are sourced directly from company ATS boards (Greenhouse, Lever, Ashby).
- Readers can apply directly through the official company postings.

Requirements:
1. 700-1000 words in a professional, helpful tone
2. Cover: role overview, key skills needed, interview preparation, salary expectations, and which companies are hiring
3. Include specific, actionable advice — not generic career advice
4. Format as clean HTML with <h2> and <p> tags (no wrappers)
5. End with a call-to-action to browse live openings

Output only the HTML content."""

    return _call(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.75,
        max_tokens=2500,
    )


def generate_weekly_digest_intro(week_start: str, new_jobs_count: int, top_companies: list, highlight_roles: list) -> str:
    """Generate an intro paragraph for a weekly digest email or page."""
    companies = ", ".join(top_companies[:5]) if top_companies else "top tech companies"
    roles = ", ".join(highlight_roles[:5]) if highlight_roles else "engineering and product roles"
    prompt = f"""Write an engaging intro paragraph for a weekly tech jobs digest.

Context:
- Week of {week_start}
- {new_jobs_count} new openings this week
- Top hiring companies: {companies}
- Standout roles: {roles}
- All jobs sourced directly from company ATS boards

Requirements:
1. 3-5 sentences, energetic but professional
2. Mention the direct-from-source advantage
3. Encourage readers to browse and apply quickly
4. Output plain text only — no HTML

Output only the intro paragraph."""

    return _call(messages=[{"role": "user", "content": prompt}], temperature=0.8, max_tokens=300)


def generate_seo_faq(company_name: str, role_type: str, common_questions: list) -> str:
    """Generate FAQ schema content for SEO."""
    questions_text = "\n".join(f"Q: {q}\nA: [answer needed]" for q in common_questions[:5])
    prompt = f"""Write SEO FAQ content about {company_name} {role_type} jobs.

Questions to answer:
{questions_text}

Requirements:
1. Each answer should be 2-4 sentences, specific and helpful
2. Include factual details where possible
3. Format as a simple Q&A list
4. Output plain text only

Output only the FAQ content."""

    return _call(messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=800)


# ═══════════════════════════════════════════════════════════════════
#  BATCH / AUTOMATION HELPERS
# ═══════════════════════════════════════════════════════════════════

def generate_for_company(company_key: str, cfg: dict, jobs: list) -> dict:
    """Generate full content package for a company in one batch call.

    Returns:
        {"blog_html": str, "meta_description": str, "faq": str}
    """
    titles = [j["title"] for j in jobs]
    unique_titles = list(dict.fromkeys(titles))[:10]  # dedupe, limit

    # Parallel calls would be ideal but for free tier we serialize to respect rate limits
    blog = generate_blog_article(
        company_name=cfg["name"],
        job_titles=unique_titles,
        ats=cfg["ats"].capitalize(),
        job_count=len(jobs),
    )
    meta = generate_company_meta_description(
        company_name=cfg["name"],
        job_count=len(jobs),
        top_roles=unique_titles,
    )
    faq_questions = [
        f"How hard is it to get hired at {cfg['name']}?",
        f"What does {cfg['name']} look for in a {unique_titles[0] if unique_titles else 'engineer'}?",
        f"Does {cfg['name']} hire remote workers?",
        f"How long is the interview process at {cfg['name']}?",
        f"What ATS does {cfg['name']} use for hiring?",
    ]
    faq = generate_seo_faq(cfg["name"], unique_titles[0] if unique_titles else "jobs", faq_questions)

    return {
        "blog_html": blog,
        "meta_description": meta,
        "faq": faq,
    }
