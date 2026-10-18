"""AI engine: role/skill matching accuracy. Pure logic - no FastAPI or database needed."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from app.ai.engine import Internship, StudentProfile, rank, recommend
from app.ai.matching import DEFAULT_WEIGHTS as W, prepare_user, rank_internships, score_internship
from app.ai.roles import resolve_roles, roles_in_title
from app.ai.semantic import semantic_similarity


def L(**kw):
    base = dict(title="Python Backend Intern", skills=["Python", "SQL"], description="", work_type="onsite",
                city="Hyderabad", eligibility=None, grad_years=[], id=1, deadline=None)
    base.update(kw)
    return NS(**base)


def U(**kw):
    base = dict(skills=["Python", "SQL"], desired_roles=["Backend Developer Intern"], location="Hyderabad",
                work_types=["onsite"], graduation_year=2027)
    base.update(kw)
    return NS(**base)


def test_title_role_detection():
    assert roles_in_title("Python Developer Intern") == {"Software Development Intern"}
    assert roles_in_title("Frontend Developer Intern") == {"Frontend Developer Intern"}  # specific beats generic
    assert roles_in_title("Machine Learning Intern") == {"AI/ML Intern"}
    assert resolve_roles("data scientist intern") == {"Data Science Intern"}
    assert resolve_roles("Underwater Basket Weaver") == set()


def test_implied_skill_gets_near_full_credit():
    r = score_internship(U(skills=["Django"]), L(skills=["Python"], title="Backend Intern"), W)
    assert r["matched_skills"] == [] and r["missing_skills"] == []
    assert r["implied_skills"][0]["required"] == "Python" and r["implied_skills"][0]["via"] == "Django"
    assert r["breakdown"]["skills"] == 0.85


def test_substitute_skill_gets_partial_credit_but_not_full():
    full = score_internship(U(skills=["TensorFlow"]), L(skills=["TensorFlow"], title="ML Intern"), W)
    part = score_internship(U(skills=["PyTorch"]), L(skills=["TensorFlow"], title="ML Intern"), W)
    none = score_internship(U(skills=["Excel"]), L(skills=["TensorFlow"], title="ML Intern"), W)
    assert full["breakdown"]["skills"] == 1.0
    assert 0.3 < part["breakdown"]["skills"] < 1.0
    assert part["related_skills"][0]["via"] == "PyTorch"
    assert none["breakdown"]["skills"] == 0.0 and none["missing_skills"] == ["TensorFlow"]


def test_title_skill_counts_double_and_generic_skill_counts_half():
    # listing: Python (in title, weight 2), Git (generic, 0.5), Docker (1)
    it = L(title="Python Intern", skills=["Python", "Git", "Docker"])
    have_title = score_internship(U(skills=["Python"]), it, W)["breakdown"]["skills"]
    have_git = score_internship(U(skills=["Git"]), it, W)["breakdown"]["skills"]
    assert have_title == round(2 / 3.5, 2) and have_git == round(0.5 / 3.5, 2)


def test_selected_role_beats_logistics():
    """A remote listing in an unrelated field must not outrank a relevant one in another city."""
    student = U(location="Hyderabad", work_types=["remote"], skills=["Python", "Django", "SQL"])
    relevant = L(title="Backend Developer Intern", skills=["Python", "Django"], work_type="onsite", city="Pune")
    irrelevant = L(title="Digital Marketing Intern", skills=["SEO"], work_type="remote", city=None, id=2)
    a, b = score_internship(student, relevant, W), score_internship(student, irrelevant, W)
    assert a["score"] > 2 * b["score"] and b["score"] < 25
    assert any("unrelated" in x for x in b["reasons"])


def test_related_roles_get_partial_credit():
    fullstack = U(desired_roles=["Full-Stack Developer Intern"])
    front = score_internship(fullstack, L(title="Frontend Developer Intern", skills=[]), W)["breakdown"]["interest"]
    mkt = score_internship(fullstack, L(title="Content Writing Intern", skills=[]), W)["breakdown"]["interest"]
    assert front >= 0.7 and mkt < 0.2
    backend_vs_front = score_internship(U(), L(title="Frontend Developer Intern", skills=[]), W)["breakdown"]["interest"]
    assert backend_vs_front < front  # Backend student is a weaker fit for Frontend than Full-Stack student


def test_role_inferred_from_skills_when_title_is_vague():
    vague = L(title="Engineering Intern", skills=["TensorFlow", "PyTorch", "Machine Learning"])
    r = score_internship(U(desired_roles=["AI/ML Intern"], skills=["Python"]), vague, W)
    assert r["breakdown"]["interest"] >= 0.7 and r["matched_role"] == "AI/ML Intern"
    unrelated = score_internship(U(desired_roles=["Digital Marketing Intern"]), vague, W)
    assert unrelated["breakdown"]["interest"] < 0.3


def test_description_evidence_when_title_and_skills_are_empty():
    it = L(title="Technology Intern", skills=[], description="You will build dashboards and KPI reports for business intelligence.")
    r = score_internship(U(desired_roles=["Data Analyst Intern"]), it, W)
    assert 0.4 <= r["breakdown"]["interest"] < 1.0


def test_skills_inferred_from_role_are_flagged_and_discounted():
    stated = score_internship(U(skills=["Python", "Java", "Node.js", "SQL", "REST APIs"]), L(title="Backend Developer Intern", skills=["Python"]), W)
    inferred = score_internship(U(skills=["Python", "Java", "Node.js", "SQL", "REST APIs"]), L(title="Backend Developer Intern", skills=[]), W)
    assert not stated["skills_inferred"] and inferred["skills_inferred"]
    assert inferred["breakdown"]["skills"] <= 0.8 and inferred["confidence"] == "medium"
    # no role in the title and no skills -> nothing invented
    blank = score_internship(U(), L(title="Summer Intern", skills=[]), W)
    assert blank["breakdown"]["skills"] is None and not blank["skills_inferred"]


def test_student_without_skills_is_not_penalised_on_skills():
    r = score_internship(U(skills=[]), L(), W)
    assert r["breakdown"]["skills"] is None and r["breakdown"]["interest"] == 1.0


def test_same_region_location_partial_credit_and_hybrid_work_type():
    near = score_internship(U(location="Delhi", work_types=["onsite"]), L(city="Gurugram", work_type="hybrid"), W)
    assert near["breakdown"]["location"] == 0.6 and near["breakdown"]["work_type"] == 0.5
    far = score_internship(U(location="Delhi"), L(city="Chennai"), W)
    assert far["breakdown"]["location"] == 0.0


def test_unmapped_free_text_role_still_works():
    r = score_internship(U(desired_roles=["quantum widget"]), L(title="Quantum Widget Intern", skills=[]), W)
    assert r["breakdown"]["interest"] == 1.0


def test_role_skill_gaps_hint():
    r = score_internship(U(skills=["Python"]), L(title="Backend Developer Intern", skills=["Python"]), W)
    assert r["role_skill_gaps"] and "Python" not in r["role_skill_gaps"]


def test_rank_orders_by_fit_then_deadline_and_hides_ineligible():
    soon, later = datetime.now(timezone.utc) + timedelta(days=2), datetime.now(timezone.utc) + timedelta(days=20)
    items = [
        L(id=1, title="Digital Marketing Intern", skills=["SEO"], work_type="remote", city=None),
        L(id=2, title="Backend Developer Intern", skills=["Python", "SQL"], deadline=later),
        L(id=3, title="Backend Developer Intern", skills=["Python", "SQL"], deadline=soon),
        L(id=4, title="Backend Developer Intern", skills=["Python", "SQL"], grad_years=[2025]),
    ]
    ranked, hidden = rank_internships(U(), items, W)
    assert [it.id for it, _ in ranked] == [3, 2, 1] and hidden == 1
    ranked_all, _ = rank_internships(U(), items, W, include_ineligible=True)
    assert len(ranked_all) == 4


def test_prepared_context_gives_identical_results():
    ctx, user = prepare_user(U()), U()
    it = L()
    assert score_internship(user, it, W) == score_internship(user, it, W, ctx=ctx)


def test_result_shape_and_levels():
    r = score_internship(U(), L(), W)
    for key in ("score", "match_level", "confidence", "breakdown", "matched_skills", "missing_skills",
                "implied_skills", "related_skills", "role_skill_gaps", "reasons", "eligibility"):
        assert key in r
    assert r["match_level"] == "strong" and r["score"] >= 75


def test_facade_and_semantic_off_by_default():
    p = StudentProfile(skills=["Python", "Pandas"], desired_roles=["Data Science Intern"], graduation_year=2027)
    listing = Internship(title="Data Science Intern", skills=["Python", "SQL", "Pandas"], grad_years=[2027])
    res = recommend(p, listing)
    assert res["matched_skills"] == ["Pandas", "Python"] and res["missing_skills"] == ["SQL"]
    assert res["eligibility"]["status"] == "eligible"
    assert semantic_similarity(p, listing) is None
    assert rank(p, [listing])[0][0] is listing
