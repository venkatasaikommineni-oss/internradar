# InternRadar AI engine (`app/ai/`)

Pure Python: no database, network or FastAPI imports. The API calls it; you can also use it standalone:

```python
from app.ai.engine import StudentProfile, Internship, recommend, rank
```

## What changed in the matcher

| Problem in the original scorer | Now |
|---|---|
| Skills matched only by exact string | **Implied skills** (Django -> Python, PyTorch -> Deep Learning/ML, Next.js -> React/JS) earn 0.85; **close substitutes** (PyTorch ~ TensorFlow, MySQL ~ PostgreSQL, React ~ Vue) earn 0.25-0.7 |
| Every listed skill weighed the same | Skills named in the **title count x2**; ubiquitous ones (Git, Agile, Excel...) count x0.5 |
| Role match = word overlap with the role name | Every curated role has a **profile** (title patterns, core skills, description cues). A listing's fit to each role comes from its **title** (strongest), its **skills**, and its **description**; **related roles** earn partial credit (Full-Stack <-> Frontend/Backend, AI/ML <-> Data Science) |
| Remote + right city could rank an irrelevant listing high | **Relevance gate**: if skills/role fit is low the whole score is scaled down (to 40% at zero relevance), so logistics cannot rescue an unrelated listing |
| Listing with no skills got no skill score | Skills are compared with the role's typical skills, **flagged** (`skills_inferred`), discounted x0.8, confidence lowered. Only when the *title* names a role; nothing is invented otherwise |
| Student with no skills scored 0 on skills | Skills factor skipped (no information), not zero |
| Location: exact city only | Same metro region (Delhi/Gurugram/Noida, Mumbai/Thane...) = 0.6 |
| Work type: exact only | Hybrid vs onsite/remote = 0.5 |
| Profile re-normalised for every listing | `prepare_user()` once per request; role analysis of listings cached (5,000 listings: ~1.5s cold, ~0.2s warm) |

## Result fields (`GET /api/recommendations`)

`score` (0-100), `match_level` (strong >=75, good >=55, partial >=35, weak), `confidence`, `breakdown` per factor,
`matched_skills`, `implied_skills`, `related_skills`, `missing_skills`, `matched_role`, `role_skill_gaps`
(what to learn for that role), `skills_inferred`, `reasons`, and `eligibility` (kept separate from the score).

## Tuning

- Weights: `W_SKILL / W_INTEREST / W_LOCATION / W_WORK_TYPE` in `.env`.
- Knowledge lives in `app/ai/roles.py` (`IMPLIES`, `RELATED_GROUPS`, `PROFILES`, `_RELATED_PAIRS`) and `app/ai/skills.py` (vocabulary). Add a skill/role there and everything picks it up; `tests/test_matching.py` shows the expected behaviour.
- Gate constants: `GATE_FLOOR`, `GATE_FULL_AT`, `INFERRED_SKILL_DISCOUNT` in `app/ai/matching.py`.
- `python scripts/benchmark_matching.py` compares against the original scorer on a small labelled set. It is a regression guard, **not** proof of real-world accuracy; calibrate with real apply/save data once you have it.

## Optional semantic layer

`pip install -r requirements-ai.txt`, `ENABLE_SEMANTIC=true`. Adds a `semantic` factor (default weight 0.15) from a pretrained sentence-embedding model; relevance gate includes it. Falls back silently to the baseline if the model cannot load.

## Limits

Scores rank; they do not predict hiring or eligibility. Listings with no deadline stay `unverified`. URL validation does not prove a link is live or safe; apply SSRF controls before server-side link checks.
