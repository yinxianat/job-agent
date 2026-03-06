"""
Resume file processing:
  - Extract text from PDF / DOCX / DOC
  - Write tailored resume to DOCX and PDF  (well-formatted)
  - File naming convention: JobTitle_Location_Company.ext
"""

import os
import re
import io
from pathlib import Path

import PyPDF2
import pdfplumber
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sanitize(name: str) -> str:
    """Remove characters not safe for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")


def build_filename(job_title: str, location: str, company: str) -> str:
    parts = [_sanitize(job_title), _sanitize(location), _sanitize(company)]
    return "_".join(p for p in parts if p) or "resume"


def _is_section_header(line: str) -> bool:
    """ALL-CAPS line with at least 3 chars — used as section heading."""
    s = line.strip()
    return (
        len(s) >= 3
        and len(s) <= 60
        and s == s.upper()
        and bool(re.search(r'[A-Z]', s))
        and not re.fullmatch(r'[\d\s\W]+', s)   # skip pure numbers/punctuation
    )


def _is_bullet(line: str) -> bool:
    s = line.strip()
    return s.startswith('•') or s.startswith('-') or s.startswith('*')


def _find_header_block(lines):
    """
    Returns (name_idx, contact_idxs) — the indices of the name line and
    contact/summary lines that appear BEFORE the first ALL-CAPS section header.
    """
    first_section = len(lines)
    for i, line in enumerate(lines):
        if _is_section_header(line):
            first_section = i
            break

    name_idx = None
    contact_idxs = []
    for i in range(first_section):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if name_idx is None:
            name_idx = i
        else:
            contact_idxs.append(i)

    return name_idx, set(contact_idxs)


# ── Text extraction ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text.strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs).strip()


def extract_resume_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    if ext in (".docx", ".doc"):
        return extract_text_from_docx(file_bytes)
    return file_bytes.decode("utf-8", errors="ignore")


# ── PDF generation ─────────────────────────────────────────────────────────────

def write_pdf(tailored_text: str, output_path: str):
    """Write a well-formatted resume PDF using ReportLab."""

    DARK_NAVY   = HexColor('#1a2744')
    SECTION_CLR = HexColor('#2c3e50')
    MID_GRAY    = HexColor('#555555')
    TEXT_CLR    = HexColor('#222222')
    RULE_CLR    = HexColor('#3d5a80')
    LIGHT_RULE  = HexColor('#bbbbbb')

    name_style = ParagraphStyle(
        'ResumeName',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1,        # centered
        textColor=DARK_NAVY,
        spaceAfter=3,
    )
    contact_style = ParagraphStyle(
        'ResumeContact',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        alignment=1,        # centered
        textColor=MID_GRAY,
        spaceAfter=1,
    )
    section_style = ParagraphStyle(
        'ResumeSection',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=SECTION_CLR,
        spaceBefore=14,
        spaceAfter=2,
    )
    bullet_style = ParagraphStyle(
        'ResumeBullet',
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        leftIndent=14,
        firstLineIndent=0,
        spaceAfter=1,
        textColor=TEXT_CLR,
    )
    normal_style = ParagraphStyle(
        'ResumeNormal',
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        spaceAfter=1,
        textColor=TEXT_CLR,
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.875 * inch,
        rightMargin=0.875 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    lines = tailored_text.splitlines()
    name_idx, contact_idxs = _find_header_block(lines)

    story = []
    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 4))
            continue

        if i == name_idx:
            story.append(Paragraph(stripped, name_style))
            story.append(HRFlowable(
                width="100%", thickness=1.5, color=RULE_CLR, spaceAfter=3, spaceBefore=0,
            ))
            continue

        if i in contact_idxs:
            story.append(Paragraph(stripped, contact_style))
            continue

        if _is_section_header(stripped):
            story.append(Paragraph(stripped, section_style))
            story.append(HRFlowable(
                width="100%", thickness=0.5, color=LIGHT_RULE, spaceAfter=4, spaceBefore=0,
            ))
            continue

        if _is_bullet(stripped):
            bullet_text = stripped.lstrip('•-* ').strip()
            story.append(Paragraph(f'\u2022\u00a0{bullet_text}', bullet_style))
            continue

        story.append(Paragraph(stripped, normal_style))

    doc.build(story)


# ── DOCX generation ────────────────────────────────────────────────────────────

def _add_paragraph_bottom_border(para):
    """Add a thin bottom border to a DOCX paragraph (section divider style)."""
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), 'AAAAAA')
    pBdr.append(bottom)
    pPr.append(pBdr)


def write_docx(tailored_text: str, output_path: str):
    """Write a well-formatted resume DOCX using python-docx."""
    lines = tailored_text.splitlines()
    name_idx, contact_idxs = _find_header_block(lines)

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin   = Inches(0.875)
        section.right_margin  = Inches(0.875)

    # Default body font
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            # Minimal spacer paragraph
            p = doc.add_paragraph()
            p.paragraph_format.space_after  = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            continue

        # ── Name ──────────────────────────────────────────────────────────────
        if i == name_idx:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_after = Pt(2)
            run = para.add_run(stripped)
            run.bold = True
            run.font.size = Pt(18)
            run.font.color.rgb = RGBColor(0x1a, 0x27, 0x44)
            # Add bottom border under name
            _add_paragraph_bottom_border(para)
            continue

        # ── Contact / header block ─────────────────────────────────────────────
        if i in contact_idxs:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_after = Pt(1)
            run = para.add_run(stripped)
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            continue

        # ── Section header (ALL-CAPS) ──────────────────────────────────────────
        if _is_section_header(stripped):
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(12)
            para.paragraph_format.space_after  = Pt(3)
            run = para.add_run(stripped)
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(0x2c, 0x3e, 0x50)
            _add_paragraph_bottom_border(para)
            continue

        # ── Bullet ─────────────────────────────────────────────────────────────
        if _is_bullet(stripped):
            bullet_text = stripped.lstrip('•-* ').strip()
            try:
                para = doc.add_paragraph(style='List Bullet')
            except KeyError:
                para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(1)
            para.paragraph_format.left_indent = Inches(0.2)
            run = para.add_run(bullet_text)
            run.font.size = Pt(10)
            continue

        # ── Normal line ────────────────────────────────────────────────────────
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(1)
        run = para.add_run(stripped)
        run.font.size = Pt(10)

    doc.save(output_path)


# ── Saving files ───────────────────────────────────────────────────────────────

def save_tailored_resume(
    tailored_text: str,
    output_folder: str,
    job_title: str,
    location: str,
    company: str,
) -> tuple[str, str]:
    """Save tailored resume as DOCX + PDF. Returns (docx_path, pdf_path)."""
    os.makedirs(output_folder, exist_ok=True)
    base_name = build_filename(job_title, location, company)
    docx_path = os.path.join(output_folder, f"{base_name}.docx")
    pdf_path  = os.path.join(output_folder, f"{base_name}.pdf")
    write_docx(tailored_text, docx_path)
    write_pdf(tailored_text,  pdf_path)
    return docx_path, pdf_path


def save_cover_letter(
    cover_letter_text: str,
    output_folder: str,
    job_title: str,
    location: str,
    company: str,
) -> tuple[str, str]:
    """Save cover letter as DOCX + PDF. Returns (docx_path, pdf_path)."""
    os.makedirs(output_folder, exist_ok=True)
    base_name = "CoverLetter_" + build_filename(job_title, location, company)
    docx_path = os.path.join(output_folder, f"{base_name}.docx")
    pdf_path  = os.path.join(output_folder, f"{base_name}.pdf")
    write_docx(cover_letter_text, docx_path)
    write_pdf(cover_letter_text,  pdf_path)
    return docx_path, pdf_path


def save_from_preview(
    tailored_text: str,
    output_folder: str,
    base_filename: str,
) -> tuple[str, str]:
    """Save an edited preview as DOCX + PDF. Returns (docx_path, pdf_path)."""
    os.makedirs(output_folder, exist_ok=True)
    docx_path = os.path.join(output_folder, f"{base_filename}.docx")
    pdf_path  = os.path.join(output_folder, f"{base_filename}.pdf")
    write_docx(tailored_text, docx_path)
    write_pdf(tailored_text,  pdf_path)
    return docx_path, pdf_path
