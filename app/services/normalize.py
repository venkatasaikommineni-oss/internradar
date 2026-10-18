"""Compatibility shim: the implementation lives in app.ai.normalize."""
from ..ai.normalize import *  # noqa: F401,F403
from ..ai.normalize import (INTERN_RE, Reject, canonical_url, clean_text, detect_work_type,  # noqa: F401
                            extract_grad_years, fingerprint, normalize_record, parse_deadline,
                            parse_duration, parse_stipend)
