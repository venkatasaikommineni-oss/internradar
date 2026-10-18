"""Synthetic ranking benchmark for the matcher.

Each student has hand-labelled relevance (2 = ideal, 1 = acceptable, 0 = wrong field) for a
shared pool of listings. We report precision@3 (share of the top 3 that are relevant) and
mean nDCG@5. Use it to compare scoring changes; it is a regression guard, not proof of
real-world accuracy (that needs click/apply data).
Run:  python scripts/benchmark_matching.py
"""
import math
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai.matching import DEFAULT_WEIGHTS, rank_internships  # noqa: E402


def L(i, title, skills, wt="onsite", city="Hyderabad", desc=""):
    return NS(id=i, title=title, skills=skills, work_type=wt, city=city, description=desc, grad_years=[],
              eligibility=None, deadline=None)


POOL = [
    L(1, "Python Backend Intern", ["Python", "Django", "SQL"]),
    L(2, "Frontend Developer Intern", ["React", "JavaScript", "CSS"], "remote", None),
    L(3, "Data Science Intern", ["Python", "Pandas", "Machine Learning"], "remote", None),
    L(4, "Digital Marketing Intern", ["SEO", "Content Writing"], "remote", None),
    L(5, "Cloud Intern", ["AWS", "Docker", "Linux"], "onsite", "Pune"),
    L(6, "Data Analyst Intern", ["Excel", "SQL", "Tableau"], "remote", None),
    L(7, "Engineering Intern", ["TensorFlow", "PyTorch", "Deep Learning"], "onsite", "Bengaluru"),
    L(8, "Full-Stack Developer Intern", ["Node.js", "React", "MongoDB"], "onsite", "Hyderabad"),
    L(9, "UI/UX Design Intern", ["Figma", "Wireframing"], "remote", None),
    L(10, "Security Analyst Intern", ["Cybersecurity", "Network Security"], "onsite", "Hyderabad"),
    L(11, "Content Writing Intern", ["Content Writing", "SEO"], "remote", None),
    L(12, "QA Testing Intern", ["Selenium", "Software Testing"], "onsite", "Hyderabad"),
]
STUDENTS = [
    (NS(skills=["Python", "Django", "SQL"], desired_roles=["Backend Developer Intern"], location="Hyderabad", work_types=["onsite"], graduation_year=2027),
     {1: 2, 8: 1, 5: 1}),
    (NS(skills=["React", "JavaScript", "CSS"], desired_roles=["Frontend Developer Intern"], location="Hyderabad", work_types=["remote"], graduation_year=2027),
     {2: 2, 8: 1, 9: 1}),
    (NS(skills=["Python", "Pandas"], desired_roles=["Data Science Intern", "AI/ML Intern"], location="Hyderabad", work_types=["remote"], graduation_year=2027),
     {3: 2, 7: 2, 6: 1}),
    (NS(skills=["PyTorch"], desired_roles=["AI/ML Intern"], location="Bengaluru", work_types=["onsite"], graduation_year=2027),
     {7: 2, 3: 1}),
    (NS(skills=["SEO"], desired_roles=["Digital Marketing Intern"], location="Hyderabad", work_types=["remote"], graduation_year=2027),
     {4: 2, 11: 1}),
    (NS(skills=["Excel", "SQL"], desired_roles=["Data Analyst Intern"], location="Hyderabad", work_types=["remote"], graduation_year=2027),
     {6: 2, 3: 1}),
    (NS(skills=["Docker", "Linux"], desired_roles=["Cloud / DevOps Intern"], location="Pune", work_types=["onsite"], graduation_year=2027),
     {5: 2, 1: 1}),
    (NS(skills=[], desired_roles=["Cybersecurity Intern"], location="Hyderabad", work_types=["onsite"], graduation_year=2027),
     {10: 2}),
]


def baseline_score(user, it):
    """The original scorer, kept verbatim for comparison (exact-skill overlap + token role overlap)."""
    import re
    W = DEFAULT_WEIGHTS
    P = [(r"front[- ]?end", "frontend"), (r"back[- ]?end", "backend"), (r"full[- ]?stack", "fullstack"),
         (r"machine learning", "ml"), (r"artificial intelligence", "ai"), (r"data scien\w+", "datascience"),
         (r"data analy\w+", "dataanalysis"), (r"cyber[- ]?security", "cybersecurity"), (r"develop\w*|engineer\w*|programmer", "dev")]
    stop = {"intern", "internship", "interns", "trainee", "and", "the", "for", "of", "a", "in", "at", "to", "with"}

    def tok(t):
        t = (t or "").lower()
        for p, r in P:
            t = re.sub(p, r, t)
        return {w for w in re.findall(r"[a-z0-9+#]+", t) if w not in stop}

    req, have = set(it.skills), set(user.skills)
    f = {"skills": len(req & have) / len(req) if req else None}
    title, extra = tok(it.title), tok(" ".join(it.skills)) | tok(it.description[:1500])
    best = 0.0
    for role in user.desired_roles:
        rt = tok(role)
        if rt:
            best = max(best, sum(1.0 if t in title else 0.5 if t in extra else 0 for t in rt) / len(rt))
    f["interest"] = best if user.desired_roles else None
    f["location"] = 1.0 if it.work_type == "remote" else (None if not (user.location and it.city) else float(it.city.lower() == user.location.lower()))
    f["work_type"] = None if not (user.work_types and it.work_type) else float(it.work_type in user.work_types)
    a = {k: v for k, v in f.items() if v is not None}
    tw = sum(W[k] for k in a)
    return sum(W[k] * v for k, v in a.items()) / tw if tw else 0.0


def ndcg(ids, rel, k=5):
    dcg = sum((2 ** rel.get(i, 0) - 1) / math.log2(n + 2) for n, i in enumerate(ids[:k]))
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum((2 ** r - 1) / math.log2(n + 2) for n, r in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def evaluate(rank_fn):
    p3 = nd = top1 = 0.0
    for user, rel in STUDENTS:
        ids = rank_fn(user)
        p3 += sum(1 for i in ids[:3] if rel.get(i, 0) > 0) / 3
        nd += ndcg(ids, rel)
        top1 += float(rel.get(ids[0], 0) == 2)
    n = len(STUDENTS)
    return p3 / n, nd / n, top1 / n


def old_rank(user):
    return [it.id for it in sorted(POOL, key=lambda it: -baseline_score(user, it))]


def new_rank(user):
    ranked, _ = rank_internships(user, POOL, DEFAULT_WEIGHTS)
    return [it.id for it, _ in ranked]


if __name__ == "__main__":
    print(f"{'':10}{'P@3':>8}{'nDCG@5':>9}{'top-1 ideal':>13}")
    for name, fn in (("original", old_rank), ("new", new_rank)):
        p3, nd, t1 = evaluate(fn)
        print(f"{name:10}{p3:8.2f}{nd:9.2f}{t1:13.2f}")
