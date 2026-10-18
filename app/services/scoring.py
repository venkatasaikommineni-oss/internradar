"""Compatibility shim: the implementation lives in app.ai.matching."""
from ..ai.matching import (DEFAULT_WEIGHTS, UserContext, eligibility, interest_match,  # noqa: F401
                           location_score, prepare_user, rank_internships, score_internship,
                           skill_match, work_type_score)
