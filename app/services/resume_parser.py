"""Resume parsing: extract plain text and skills from PDF/DOCX uploads."""
from __future__ import annotations

import io
import logging
import os
import re

log = logging.getLogger("internradar.resume")


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes. Returns plain text."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
        return "\n".join(parts)
    except Exception:
        log.exception("PDF extraction failed")
        return ""


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(parts)
    except Exception:
        log.exception("DOCX extraction failed")
        return ""


def extract_text(content: bytes, filename: str) -> str:
    """Auto-detect format and extract text."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if name.endswith(".docx"):
        return extract_text_from_docx(content)
    if name.endswith(".txt"):
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""


def extract_skills_from_text(text: str) -> list[str]:
    """Extract canonical skills from resume text using the AI skills vocabulary."""
    from ..ai.skills import extract_skills
    return extract_skills(text)


def extract_contact_info(text: str) -> dict:
    """Try to parse email, phone from text."""
    email_re = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    phone_re = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}")
    emails = email_re.findall(text)
    phones = phone_re.findall(text)
    return {
        "email": emails[0] if emails else None,
        "mobile": phones[0] if phones else None,
    }
