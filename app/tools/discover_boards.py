"""Find which companies publish a public job board, and write them into sources.json.

    python -m app.tools.discover_boards data/india_companies.txt            # report only
    python -m app.tools.discover_boards data/india_companies.txt --write    # merge into sources.json
    python -m app.tools.discover_boards --company "Razorpay" --company "Pine Labs" --write

Greenhouse, Lever and Ashby each expose a PUBLIC job-board API meant for exactly this
(listing a company's open roles). For every company name this probes the likely board
names on those APIs, reports what it found (jobs, internships, internships in India,
sample titles) and, with --write, merges the boards into sources.json.

Matching a name to a board is a guess (a short name can belong to a different company),
so look at the sample titles before keeping a board. Requests go through the shared,
rate-limited HTTP layer."""
import argparse
import json
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from ..config import settings
from ..services.geo import is_india
from ..services.sources import net
from ..services.sources.base import looks_like_internship
from ..services.sources.mappers import ashby_to_raw, greenhouse_to_raw, lever_to_raw

_GENERIC = {
    "technologies", "technology", "labs", "lab", "pvt", "ltd", "limited", "private", "inc", "india",
    "software", "solutions", "systems", "group", "services", "tech",
}


def slug_variants(name: str, min_length: int = 4) -> list[str]:
    """Likely board names for a company: 'Pine Labs' -> pinelabs, pine-labs."""
    n = re.sub(r"\.(com|io|ai|in|co)\b", "", name.lower().strip().replace("&", " and "))
    words = [w for w in re.split(r"[^a-z0-9]+", n) if w]
    if not words:
        return []
    variants = ["".join(words), "-".join(words)]
    core = [w for w in words if w not in _GENERIC]
    if core and core != words:
        variants += ["".join(core), "-".join(core)]
    out: list[str] = []
    for v in variants:
        if len(v) >= min_length and v not in out:
            out.append(v)
    return out


def _summary(ats: str, slug: str, raws: list[dict]) -> dict:
    interns = [r for r in raws if looks_like_internship(r)]
    return {
        "ats": ats,
        "slug": slug,
        "jobs": len(raws),
        "interns": len(interns),
        "india_interns": sum(1 for r in interns if is_india(r.get("location"))),
        "sample": [r.get("title") for r in interns[:3]],
    }


def _json(url: str, params: dict | None = None):
    try:
        r = net.request(url, params=params, retries=1)
        return r.json() if r.status_code == 200 else None
    except (net.FetchError, ValueError):
        return None


def probe_greenhouse(slug: str) -> dict | None:
    data = _json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return None
    found = _summary("greenhouse", slug, [greenhouse_to_raw(j) for j in jobs])
    meta = _json(f"https://boards-api.greenhouse.io/v1/boards/{slug}")
    found["board_name"] = meta.get("name") if isinstance(meta, dict) else None
    return found


def probe_lever(slug: str) -> dict | None:
    data = _json(f"https://api.lever.co/v0/postings/{slug}", {"mode": "json", "limit": 100})
    if not isinstance(data, list) or not data:  # an empty list cannot be told apart from an unknown name
        return None
    return _summary("lever", slug, [lever_to_raw(p) for p in data])


def probe_ashby(slug: str) -> dict | None:
    data = _json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return None
    return _summary("ashby", slug, [ashby_to_raw(j) for j in jobs if j.get("isListed") is not False])


PROBES = {"greenhouse": probe_greenhouse, "lever": probe_lever, "ashby": probe_ashby}


def _first_hit(company: str, ats: str, min_length: int) -> dict | None:
    for slug in slug_variants(company, min_length):
        found = PROBES[ats](slug)
        if found:
            return {**found, "company": company}
    return None


def discover(companies: list[str], workers: int = 6, min_length: int = 4, providers=("greenhouse", "lever", "ashby")) -> list[dict]:
    jobs = [(c, a) for c in dict.fromkeys(companies) for a in providers]
    with ThreadPoolExecutor(max(1, workers)) as pool:
        results = list(pool.map(lambda ca: _first_hit(ca[0], ca[1], min_length), jobs))
    return [r for r in results if r]


# ---------- sources.json ----------
_KEYS = {"greenhouse": "boards", "lever": "companies", "ashby": "boards"}


def merge_sources(existing, found: list[dict]) -> dict:
    """Add found boards to a sources.json structure without duplicating what is there."""
    cfg = {"sources": list(existing.get("sources", []) if isinstance(existing, dict) else existing or [])}
    for f in found:
        key = _KEYS[f["ats"]]
        entry = next((s for s in cfg["sources"] if s.get("type") == f["ats"] and key in s), None)
        if entry is None:
            entry = {"type": f["ats"], key: []}
            cfg["sources"].append(entry)
        have = {(b if isinstance(b, str) else b.get("token", "")).lower() for b in entry[key]}
        if f["slug"].lower() not in have:
            entry[key].append({"token": f["slug"], "company": f.get("board_name") or f["company"]})
    return cfg


def _read_names(path: str | None, extra: list[str]) -> list[str]:
    names = list(extra)
    if path:
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names_file", nargs="?", help="text file, one company per line")
    ap.add_argument("--company", action="append", default=[], help="a company name (repeatable)")
    ap.add_argument("--out", default=settings.sources_file, help="sources.json to merge into (default: %(default)s)")
    ap.add_argument("--write", action="store_true", help="write the boards found into --out")
    ap.add_argument("--only-interns", action="store_true", help="keep only boards that list internships right now")
    ap.add_argument("--min-length", type=int, default=4, help="ignore board names shorter than this (avoids look-alikes)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)

    names = _read_names(args.names_file, args.company)
    if not names:
        ap.error("give a names file and/or --company")
    print(f"probing {len(names)} companies on Greenhouse / Lever / Ashby ...", file=sys.stderr)
    found = discover(names, args.workers, args.min_length)
    if args.only_interns:
        found = [f for f in found if f["interns"]]

    print(f"\n{'company':26} {'ats':10} {'board':24} {'jobs':>5} {'interns':>8} {'india':>6}  sample")
    for f in sorted(found, key=lambda f: (-f["india_interns"], -f["interns"], f["company"])):
        print(f"{f['company'][:25]:26} {f['ats']:10} {f['slug'][:23]:24} {f['jobs']:>5} {f['interns']:>8} {f['india_interns']:>6}  {'; '.join(t for t in f['sample'] if t)[:60]}")
    print(f"\n{len(found)} board(s) found, {sum(1 for f in found if f['interns'])} with internships now, "
          f"{sum(1 for f in found if f['india_interns'])} with internships in India")

    if args.write:
        path = pathlib.Path(args.out)
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"sources": []}
        path.write_text(json.dumps(merge_sources(existing, found), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path} - restart the server (or POST /api/admin/import) to start collecting")
    elif found:
        print("re-run with --write to add them to sources.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
