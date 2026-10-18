"""Compatibility shim: the implementation lives in app.ai.skills."""
from ..ai.skills import *  # noqa: F401,F403
from ..ai.skills import (  # noqa: F401
    SKILLS, ROLES, SPECIALIZATIONS,
    canonical_role, canonical_skill, canonical_specialization,
    extract_skills, skills_blob,
    suggest_roles, suggest_skills, suggest_specializations,
)
