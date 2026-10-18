"""Smoke test: python -m app.ai"""
from .engine import Internship, StudentProfile, recommend

p = StudentProfile(skills=["Python", "Django", "SQL"], desired_roles=["Backend Developer Intern"], work_types=["remote"])
i = Internship(title="Python Backend Intern", company="Example", skills=["Python", "SQL", "Pandas"], work_type="remote")
print(recommend(p, i))
