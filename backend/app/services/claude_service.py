"""
Claude AI integration for resume tailoring, cover letter generation,
and AI-powered job match scoring.
Uses the Anthropic Python SDK with the claude-opus-4-6 model.
"""

import json
import logging
import re
from typing import List, Dict, Any, Tuple, Optional

import anthropic
from ..config import settings

log = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── Resume tailoring ───────────────────────────────────────────────────────────

TAILOR_SYSTEM_PROMPT = """You are an expert resume writer and career coach with 15+ years of experience.
Your task is to tailor a candidate's resume for a specific job posting.

Guidelines:
- Preserve ALL factual information (dates, job titles, companies, education, certifications)
- Reorder and rephrase bullet points to best match the job description keywords and requirements
- Prominently feature any candidate skills/keywords that match the role
- Use strong action verbs and quantifiable achievements where possible
- Match the tone and vocabulary of the job description
- Highlight the skills that directly align with the role
- Keep the resume to a maximum of 2 pages
- Output ONLY the final tailored resume in clean plain text (no markdown formatting)
- Maintain professional formatting with clear section headers in ALL CAPS"""


async def tailor_resume(
    resume_text: str,
    job_title: str,
    company: str,
    location: str,
    job_description: str,
    extra_skills: str = "",
) -> str:
    """Tailor the resume for a specific job, optionally injecting extra skills/keywords."""
    client = get_client()

    skills_section = (
        f"\n=== CANDIDATE'S ADDITIONAL SKILLS & KEYWORDS TO HIGHLIGHT ===\n{extra_skills}"
        if extra_skills.strip() else ""
    )

    user_message = f"""Please tailor the following resume for this specific job opportunity.

=== JOB DETAILS ===
Title:    {job_title}
Company:  {company}
Location: {location}

=== JOB DESCRIPTION ===
{job_description}
{skills_section}

=== ORIGINAL RESUME ===
{resume_text}

Produce a fully tailored version optimised for this role.
Output ONLY the resume content — no introductory text, no explanations."""

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=4096,
        system=TAILOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


# ── Cover letter generation ────────────────────────────────────────────────────

COVER_LETTER_SYSTEM_PROMPT = """You are an expert career coach who writes compelling, personalised cover letters.

Guidelines:
- Write a professional cover letter of 3-4 paragraphs (approx 300-400 words)
- Opening: express genuine interest in the specific role and company
- Body paragraph 1: match 2-3 key skills/achievements from the resume to the job requirements
- Body paragraph 2: demonstrate knowledge of the company culture/mission and explain why you are a great fit
- Closing: confident call-to-action, thank the reader
- Use first-person, confident, professional tone
- Do NOT use generic filler phrases like "I am writing to express my interest..."
- Output ONLY the cover letter text (no subject line, no markdown)
- Start directly with "Dear Hiring Manager," or a specific name if available"""


async def generate_cover_letter(
    resume_text: str,
    job_title: str,
    company: str,
    location: str,
    job_description: str,
    company_description: str = "",
    extra_skills: str = "",
) -> str:
    """Generate a tailored cover letter for a specific job application."""
    client = get_client()

    company_context = (
        f"\n=== COMPANY BACKGROUND ===\n{company_description}"
        if company_description.strip() else ""
    )
    skills_context = (
        f"\n=== CANDIDATE'S KEY SKILLS TO FEATURE ===\n{extra_skills}"
        if extra_skills.strip() else ""
    )

    user_message = f"""Write a compelling cover letter for this job application.

=== JOB DETAILS ===
Title:    {job_title}
Company:  {company}
Location: {location}

=== JOB DESCRIPTION ===
{job_description}
{company_context}
{skills_context}

=== CANDIDATE'S RESUME (for reference) ===
{resume_text}

Write the cover letter now. Output only the letter text."""

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=COVER_LETTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


# ── Company research ───────────────────────────────────────────────────────────

COMPANY_RESEARCH_PROMPT = """You are a concise business researcher.
Given a company name and job title, write a 2-3 sentence description of the company:
what they do, their industry, approximate size/stage, and any notable culture or values.
Be factual and professional. Output ONLY the description, no preamble."""


async def research_company(company: str, job_title: str) -> str:
    """Return a short company description for the resume tracker and cover letter context."""
    client = get_client()
    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=256,
        system=COMPANY_RESEARCH_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Company: {company}\nRole being applied for: {job_title}"
        }],
    )
    return response.content[0].text


# ── Job match scoring ─────────────────────────────────────────────────────────

SCORE_SYSTEM_PROMPT = """You are a senior career advisor and talent-matching expert.
Your job is to evaluate how well each job listing fits a candidate based on:
1. Alignment between the job requirements and the candidate's resume / skills / experience
2. Alignment with the candidate's stated career wishes and goals
3. Industry / seniority fit

Return ONLY a valid JSON array — no markdown fences, no commentary — in this exact format:
[
  {"index": 0, "score": 85, "reason": "Strong match: your 5-yr Python background directly maps to the role's core requirement; the AI/ML focus aligns with your stated interest in machine-learning roles."},
  ...
]

Scoring guide:
90-100 = Exceptional fit — almost every requirement matches
75-89  = Strong fit — most key requirements match
60-74  = Good fit — solid overlap with some gaps
40-59  = Moderate fit — some relevant experience, notable gaps
20-39  = Weak fit — limited overlap
0-19   = Poor fit — significant mismatch

Keep each reason to 1-2 sentences; be specific about WHY it scores that way."""


async def score_jobs(
    jobs: List[Dict[str, Any]],
    profile: str = "",
    wishes: str = "",
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Score each job against the candidate profile + wishes using Claude.

    Returns:
        (scored_jobs, error_message, error_type)
        scored_jobs: list of dicts with index, score, reason
        error_message: human-readable string if an error occurred, else None
        error_type: "overloaded" | "rate_limit" | "api_error" | None
    """
    if not jobs:
        return [], None, None

    client = get_client()

    # Build candidate profile block
    profile_lines = []
    if profile.strip():
        profile_lines.append(f"=== CANDIDATE PROFILE / RESUME ===\n{profile.strip()[:3000]}")
    if wishes.strip():
        profile_lines.append(f"=== WHAT THE CANDIDATE IS LOOKING FOR ===\n{wishes.strip()[:500]}")
    if not profile_lines:
        profile_lines.append("=== CANDIDATE PROFILE ===\n(No profile provided — score purely on job quality and general desirability.)")

    candidate_block = "\n\n".join(profile_lines)

    # Build jobs block — cap description at 300 chars per job to stay within tokens
    jobs_block_lines = []
    for i, job in enumerate(jobs):
        desc = (job.get("description") or "")[:300].replace("\n", " ")
        jobs_block_lines.append(
            f"Job {i} | Title: {job.get('title','N/A')} | Company: {job.get('company','N/A')} "
            f"| Location: {job.get('location','N/A')}\nDescription: {desc or 'No description available.'}"
        )
    jobs_block = "\n\n".join(jobs_block_lines)

    user_message = f"""{candidate_block}

=== JOBS TO SCORE ({len(jobs)} total) ===
{jobs_block}

Score every job (indexes 0 to {len(jobs)-1}) for this candidate.
Return ONLY the JSON array."""

    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=SCORE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if Claude included them anyway
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw, flags=re.IGNORECASE)

        parsed = json.loads(raw)
        return parsed, None, None

    except anthropic.APIStatusError as exc:
        if exc.status_code == 529:
            msg = (
                "Claude API is currently overloaded. Your usage credits may also be exhausted. "
                "Please wait a few minutes and try again when your credits are renewed."
            )
            log.warning("Claude overloaded (529) during job scoring: %s", exc)
            return [], msg, "overloaded"
        if exc.status_code == 429:
            msg = (
                "Claude API rate limit reached — you may have run out of credits for this period. "
                "Please wait for your credit allowance to renew and try again."
            )
            log.warning("Claude rate-limited (429) during job scoring: %s", exc)
            return [], msg, "rate_limit"
        log.error("Claude API error during job scoring: %s", exc)
        return [], f"Claude API error ({exc.status_code}): {exc.message}", "api_error"

    except anthropic.APIConnectionError as exc:
        log.error("Claude connection error: %s", exc)
        return [], "Could not reach the Claude API. Check your internet connection and try again.", "api_error"

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.error("Failed to parse Claude score response: %s", exc)
        return [], "Received an unexpected response from Claude. Please try again.", "api_error"
