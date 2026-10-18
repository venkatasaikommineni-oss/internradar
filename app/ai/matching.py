"""Explainable internship <-> student matching.

Pure functions, duck-typed on any object with the attributes used below (ORM rows,
dataclasses or SimpleNamespace). No database, network or framework imports.

How a score is built
--------------------
factors (each 0..1, or None when the data to judge it is missing):
  skills     weighted coverage of the listing's skills. Exact match = 1.0, implied
             (Django -> Python) = 0.85, close substitute (PyTorch ~ TensorFlow) = 0.3-0.7.
             Skills named in the job title count double; ubiquitous ones (Git...) half.
  interest   how well the listing fits the student's *selected roles*, from the title
             (strongest), the listing's skills and its description; related roles
             (Frontend <-> Full-Stack) earn partial credit.
  location   same city 1.0, same metro region 0.6, remote 1.0
  work_type  matches preference 1.0, hybrid-vs-other 0.5
  semantic   optional embedding similarity (see semantic.py)
Missing factors are dropped and the rest renormalised, so absent data neither
helps nor hurts. A *relevance gate* then scales the result down when the student's
skills/roles clearly do not fit, so logistics (a remote listing, the right city)
can never lift an irrelevant internship to the top.
Eligibility (graduation year) stays separate from the score.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .geo import same_region
from .roles import (
    GENERIC_SKILLS, GENERIC_WEIGHT, IMPLIED_CREDIT, IMPLIES, PROFILES, RELATED_GROUPS,
    RELATED_ROLES, TITLE_WEIGHT, resolve_roles, roles_in_title,
)
from .semantic import semantic_similarity
from .skills import canonical_skill, extract_skills

DEFAULT_WEIGHTS = {"skills": 0.55, "interest": 0.20, "location": 0.15, "work_type": 0.10}
RELEVANCE_FACTORS = ("skills", "interest", "semantic")
INFERRED_SKILL_DISCOUNT = 0.8   # skills inferred from the role (not stated by the listing) count less
GATE_FLOOR = 0.4                # score multiplier when relevance is 0
GATE_FULL_AT = 0.5              # relevance at/above this is not penalised


# ------------------------------------------------------------------ user side
@dataclass(frozen=True)
class UserContext:
    """Everything derived from the student's profile, computed once per request."""
    skills: frozenset
    implied: dict = field(default_factory=dict)       # skill -> the user skill that implies it
    roles: frozenset = frozenset()                    # curated roles the student selected
    free_roles: tuple = ()                            # selected roles we could not map
    location: str | None = None
    work_types: frozenset = frozenset()
    graduation_year: int | None = None
    resume_skills: frozenset = frozenset()            # skills extracted from resume (may overlap)


def _clean_skills(raw) -> frozenset:
    out = set()
    for s in raw or []:
        c = canonical_skill(s)
        if c:
            out.add(c)
    return frozenset(out)


def prepare_user(user) -> UserContext:
    """Normalise a profile once; pass the result to score_internship() when scoring many listings."""
    if isinstance(user, UserContext):
        return user
    # Merge profile skills + resume skills for broader matching
    raw_skills = list(getattr(user, "skills", None) or [])
    resume_raw = list(getattr(user, "resume_skills", None) or [])
    all_raw = list(dict.fromkeys(raw_skills + resume_raw))  # preserve order, dedupe
    skills = _clean_skills(all_raw)
    resume_skills = _clean_skills(resume_raw)
    implied: dict[str, str] = {}
    frontier = {s: s for s in skills}
    for _ in range(3):  # transitive closure (Next.js -> React -> JavaScript)
        nxt = {}
        for have, origin in frontier.items():
            for v in IMPLIES.get(have, ()):
                if v not in skills and v not in implied:
                    implied[v] = origin
                    nxt[v] = origin
        if not nxt:
            break
        frontier = nxt
    roles, free = set(), []
    for r in getattr(user, "desired_roles", None) or []:
        hit = resolve_roles(r)
        if hit:
            roles |= hit
        elif (r or "").strip():
            free.append(r)
    return UserContext(
        skills=skills, implied=implied, roles=frozenset(roles), free_roles=tuple(free),
        location=(getattr(user, "location", None) or None),
        work_types=frozenset(getattr(user, "work_types", None) or ()),
        graduation_year=getattr(user, "graduation_year", None),
        resume_skills=resume_skills,
    )


# ------------------------------------------------------------------ skills
@lru_cache(maxsize=16384)
def _title_skills(title: str) -> frozenset:
    return frozenset(extract_skills(title))


def _skill_weight(skill: str, title_skills) -> float:
    if skill in title_skills:
        return TITLE_WEIGHT
    return GENERIC_WEIGHT if skill in GENERIC_SKILLS else 1.0


def _related_credit(skill: str, have: frozenset) -> tuple[float, str | None]:
    best, via = 0.0, None
    for group, credit in RELATED_GROUPS:
        if skill in group and credit > best:
            hit = sorted(have & (group - {skill}))
            if hit:
                best, via = credit, hit[0]
    return best, via


def skill_match(ctx: UserContext, required, title: str = "") -> dict:
    """Weighted coverage of `required` skills by the student's skills."""
    title_skills = _title_skills(title or "")
    matched, implied, related, missing = [], [], [], []
    got = total = 0.0
    for r in sorted(set(required)):
        w = _skill_weight(r, title_skills)
        total += w
        if r in ctx.skills:
            matched.append(r)
            got += w
        elif r in ctx.implied:
            implied.append({"required": r, "via": ctx.implied[r], "credit": IMPLIED_CREDIT})
            got += w * IMPLIED_CREDIT
        else:
            credit, via = _related_credit(r, ctx.skills)
            if credit:
                related.append({"required": r, "via": via, "credit": credit})
                got += w * credit
            else:
                missing.append(r)
    return {
        "coverage": (got / total) if total else None,
        "matched": matched, "implied": implied, "related": related, "missing": missing,
    }


# ------------------------------------------------------------------ roles
@lru_cache(maxsize=32768)
def _role_affinity(title: str, skills: tuple, desc: str) -> dict:
    """How strongly a listing belongs to each curated role (0..1)."""
    skillset = set(skills)
    d = desc.lower()
    title_roles = roles_in_title(title)
    specific_title = any(not PROFILES[r].generic for r in title_roles)
    damp = 0.6 if specific_title else 1.0  # a clear, specific title makes weaker evidence less relevant
    direct = {}
    for name, p in PROFILES.items():
        if name in title_roles:
            direct[name] = 1.0
            continue
        hits = sum(1 for c in p.core if c in skillset)
        skill_ev = 0.7 * min(1.0, hits / 3)
        desc_ev = 0.45 if (d and p.desc_re.search(d)) else 0.0
        direct[name] = max(skill_ev, desc_ev) * damp
    out = {}
    for name in PROFILES:
        best = direct[name]
        for other, w in RELATED_ROLES.get(name, {}).items():
            best = max(best, w * direct[other])
        out[name] = round(best, 3)
    return out


def listing_roles(it) -> dict:
    return _role_affinity(getattr(it, "title", "") or "", tuple(sorted(getattr(it, "skills", None) or ())),
                          (getattr(it, "description", "") or "")[:1500])


_PHRASES = [
    (r"front[- ]?end", "frontend"), (r"back[- ]?end", "backend"), (r"full[- ]?stack", "fullstack"),
    (r"machine learning", "ml"), (r"artificial intelligence", "ai"),
    (r"data scien\w+", "datascience"), (r"data analy\w+", "dataanalysis"),
    (r"cyber[- ]?security", "cybersecurity"), (r"develop\w*|engineer\w*|programmer", "dev"),
]
_STOP = {"intern", "internship", "interns", "trainee", "and", "the", "for", "of", "a", "in", "at", "to", "with"}


def _tokens(text) -> set:
    t = (text or "").lower()
    for pat, rep in _PHRASES:
        t = re.sub(pat, rep, t)
    return {w for w in re.findall(r"[a-z0-9+#]+", t) if w not in _STOP}


def _free_text_interest(role: str, it) -> float:
    """Fallback for role text we cannot map to a curated role: token overlap."""
    rt = _tokens(role)
    if not rt:
        return 0.0
    title = _tokens(getattr(it, "title", ""))
    extra = _tokens(" ".join(getattr(it, "skills", None) or [])) | _tokens((getattr(it, "description", "") or "")[:1500])
    return sum(1.0 if t in title else 0.5 if t in extra else 0.0 for t in rt) / len(rt)


def interest_match(ctx: UserContext, it) -> tuple[float | None, str | None]:
    """(score, best matching selected role) -- None when the student selected no roles."""
    if not ctx.roles and not ctx.free_roles:
        return None, None
    best, best_role = 0.0, None
    if ctx.roles:
        aff = listing_roles(it)
        for r in sorted(ctx.roles):
            if aff.get(r, 0.0) > best:
                best, best_role = aff[r], r
    for r in ctx.free_roles:
        s = _free_text_interest(r, it)
        if s > best:
            best, best_role = s, r
    return best, best_role


# ------------------------------------------------------------------ logistics
def location_score(ctx: UserContext, it) -> float | None:
    if getattr(it, "work_type", None) == "remote":
        return 1.0
    city = getattr(it, "city", None)
    if not ctx.location or not city:
        return None
    if city.lower() == ctx.location.lower():
        return 1.0
    return 0.6 if same_region(city, ctx.location) else 0.0


def work_type_score(ctx: UserContext, it) -> float | None:
    wt = getattr(it, "work_type", None)
    if not ctx.work_types or not wt:
        return None
    if wt in ctx.work_types:
        return 1.0
    return 0.5 if (wt == "hybrid" or "hybrid" in ctx.work_types) else 0.0


def eligibility(user, it) -> dict:
    """Mandatory constraints are kept separate from the similarity score."""
    grad = user.graduation_year if isinstance(user, UserContext) else getattr(user, "graduation_year", None)
    years = getattr(it, "grad_years", None) or []
    if years and grad:
        if grad in years:
            return {"status": "eligible", "detail": f"Open to {', '.join(map(str, years))} graduates."}
        return {"status": "not_eligible",
                "detail": f"Listing is for {', '.join(map(str, years))} graduates; your graduation year is {grad}."}
    if years and not grad:
        return {"status": "unknown",
                "detail": f"Listing targets {', '.join(map(str, years))} graduates; add your graduation year to check."}
    return {"status": "unknown",
            "detail": "Eligibility not specified in the listing." if not getattr(it, "eligibility", None) else "See stated requirements."}


# ------------------------------------------------------------------ scoring
def _level(score: float) -> str:
    return "strong" if score >= 75 else "good" if score >= 55 else "partial" if score >= 35 else "weak"


def score_internship(user, it, weights: dict[str, float] | None = None, ctx: UserContext | None = None) -> dict:
    """Score one listing for one student. Pass `ctx=prepare_user(user)` when looping."""
    w = weights or DEFAULT_WEIGHTS
    ctx = ctx or prepare_user(user)
    title = getattr(it, "title", "") or ""
    required = list(getattr(it, "skills", None) or [])

    interest, best_role = interest_match(ctx, it)

    # skills: stated by the listing, or (flagged, discounted) inferred from a title-derived role
    skills_inferred = False
    inferred_role = None
    if not required:
        title_roles = sorted(roles_in_title(title))
        if title_roles:
            pick = next((r for r in title_roles if r in ctx.roles), title_roles[0])
            required, skills_inferred, inferred_role = list(PROFILES[pick].core), True, pick
    sm = skill_match(ctx, required, title) if required else None
    skills_factor = None
    if sm and sm["coverage"] is not None and (ctx.skills or ctx.implied):
        skills_factor = sm["coverage"] * (INFERRED_SKILL_DISCOUNT if skills_inferred else 1.0)

    factors = {
        "skills": skills_factor,
        "interest": interest,
        "location": location_score(ctx, it),
        "work_type": work_type_score(ctx, it),
    }
    if "semantic" in w:
        factors["semantic"] = semantic_similarity(user, it) if not isinstance(user, UserContext) else None

    avail = {k: v for k, v in factors.items() if v is not None and w.get(k, 0) > 0}
    total_w = sum(w[k] for k in avail)
    base = sum(w[k] * v for k, v in avail.items()) / total_w if total_w else 0.0

    rel = {k: v for k, v in avail.items() if k in RELEVANCE_FACTORS}
    rel_w = sum(w[k] for k in rel)
    relevance = sum(w[k] * v for k, v in rel.items()) / rel_w if rel_w else None
    gate = 1.0 if relevance is None else GATE_FLOOR + (1 - GATE_FLOOR) * min(1.0, relevance / GATE_FULL_AT)
    score = round(base * gate * 100, 1)

    matched = sm["matched"] if sm and not skills_inferred else (sm["matched"] if sm else [])
    reasons = []
    if skills_inferred:
        reasons.append(f"The listing names no skills, so your skills were compared with those typical for a {inferred_role} (lower confidence).")
    elif matched:
        reasons.append(f"You already have {len(matched)} of {len(required)} listed skills: {', '.join(matched)}.")
    if sm and sm["implied"]:
        reasons.append("Your skills imply: " + ", ".join(f"{i['required']} (from {i['via']})" for i in sm["implied"]) + ".")
    if sm and sm["related"]:
        reasons.append("Close substitutes count partly: " + ", ".join(f"{i['required']} ~ {i['via']}" for i in sm["related"]) + ".")
    if required and sm and not (matched or sm["implied"] or sm["related"]) and ctx.skills:
        reasons.append("None of your skills overlap with the listed requirements.")
    if not required:
        reasons.append("The listing does not state required skills, so skill match was not scored.")
    if interest is not None:
        if best_role and interest >= 1.0 and best_role in roles_in_title(title):
            reasons.append(f"Title matches your desired role ({best_role}).")
        elif best_role and interest >= 0.5:
            reasons.append(f"Fits your desired role ({best_role}).")
        elif interest < 0.2:
            reasons.append("This listing looks unrelated to your selected roles.")
    if getattr(it, "work_type", None) == "remote":
        reasons.append("Remote - location is not a constraint.")
    elif factors["location"] == 1.0:
        reasons.append(f"Located in your preferred city ({it.city}).")
    elif factors["location"] == 0.6:
        reasons.append(f"Located in {it.city}, in the same region as {ctx.location}.")
    elif factors["location"] == 0.0:
        reasons.append(f"Located in {it.city}, not your preferred city.")
    if factors["work_type"] == 1.0:
        reasons.append(f"Work type ({it.work_type}) fits your preference.")
    elif factors["work_type"] == 0.5:
        reasons.append(f"Work type ({it.work_type}) is partly compatible with your preference.")
    elif factors["work_type"] == 0.0:
        reasons.append(f"Work type ({it.work_type}) differs from your preference.")
    if factors.get("semantic") is not None:
        reasons.append("A language model compared the meaning of your roles and skills with this listing.")

    # learning hint: core skills of the matched role the student does not have yet
    gaps = []
    if best_role in PROFILES and interest and interest >= 0.5:
        gaps = [c for c in PROFILES[best_role].core if c not in ctx.skills and c not in ctx.implied][:4]

    n_core = sum(1 for k in ("skills", "interest") if factors[k] is not None)
    confidence = "high" if n_core == 2 and not skills_inferred else "medium" if n_core >= 1 else "low"

    # resume_boost: True when any matched skill came exclusively from the resume
    profile_only_skills = ctx.skills - ctx.resume_skills
    resume_boost = bool(ctx.resume_skills and matched and any(s in ctx.resume_skills and s not in profile_only_skills for s in matched))
    if resume_boost:
        reasons.append("Your uploaded resume provided additional skill evidence for this match.")

    return {
        "score": score,
        "match_level": _level(score),
        "confidence": confidence,
        "breakdown": {k: (round(v, 2) if v is not None else None) for k, v in factors.items()},
        "matched_skills": matched,
        "missing_skills": sm["missing"] if sm else [],
        "implied_skills": sm["implied"] if sm else [],
        "related_skills": sm["related"] if sm else [],
        "skills_inferred": skills_inferred,
        "matched_role": best_role if (interest or 0) >= 0.5 else None,
        "role_skill_gaps": gaps,
        "reasons": reasons,
        "resume_boost": resume_boost,
        "eligibility": {**eligibility(ctx, it), "requirements": getattr(it, "eligibility", None)},
    }


def rank_internships(user, listings, weights=None, *, min_score: float = 0.0, include_ineligible: bool = False):
    """Score and sort many listings. Returns (ranked [(listing, result)], hidden_ineligible_count).
    Ties: higher score, then sooner deadline, then newest id."""
    ctx = prepare_user(user)
    if isinstance(user, UserContext):
        sem_user = None
    else:
        sem_user = user
    ranked, hidden = [], 0
    for it in listings:
        res = score_internship(sem_user if sem_user is not None else ctx, it, weights, ctx=ctx)
        if res["eligibility"]["status"] == "not_eligible" and not include_ineligible:
            hidden += 1
            continue
        if res["score"] >= min_score:
            ranked.append((it, res))

    def key(pair):
        it, res = pair
        d = getattr(it, "deadline", None)
        return (-res["score"], d.timestamp() if d else float("inf"), -(getattr(it, "id", 0) or 0))

    ranked.sort(key=key)
    return ranked, hidden
