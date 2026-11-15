"""Source jobs from public ATS boards into SQLite.

Run standalone to refresh the local job store:

    python3 -m app.sourcer
"""
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

MAX_JOBS_PER_COMPANY = 50
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs.db")

# Boards verified to answer publicly. fortune500 is set only for companies on
# Fortune's US 500 list that publish a public Greenhouse/Lever/Ashby board —
# Google, Microsoft and Amazon use Workday or their own portals, so they can't
# be sourced here.
COMPANIES = {
    "airbnb": {"name": "Airbnb", "ats": "greenhouse", "slug": "airbnb"},
    "cloudflare": {"name": "Cloudflare", "ats": "greenhouse", "slug": "cloudflare"},
    "coinbase": {"name": "Coinbase", "ats": "greenhouse", "slug": "coinbase"},
    "datadog": {"name": "Datadog", "ats": "greenhouse", "slug": "datadog"},
    "gitlab": {"name": "GitLab", "ats": "greenhouse", "slug": "gitlab"},
    "hp": {"name": "HP", "ats": "greenhouse", "slug": "hp", "fortune500": True},
    "pinterest": {"name": "Pinterest", "ats": "greenhouse", "slug": "pinterest"},
    "reddit": {"name": "Reddit", "ats": "greenhouse", "slug": "reddit"},
    "stripe": {"name": "Stripe", "ats": "greenhouse", "slug": "stripe"},
    "openai": {"name": "OpenAI", "ats": "ashby", "slug": "openai"},
    "ramp": {"name": "Ramp", "ats": "ashby", "slug": "ramp"},
    "palantir": {"name": "Palantir", "ats": "lever", "slug": "palantir"},
    "spotify": {"name": "Spotify", "ats": "lever", "slug": "spotify"},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    function TEXT,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    fortune500 INTEGER NOT NULL DEFAULT 0,
    posted TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_company ON jobs(company);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def db_path() -> str:
    return os.environ.get("JOBS_DB", DEFAULT_DB)


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    if "posted" not in {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}:
        conn.execute("ALTER TABLE jobs ADD COLUMN posted TEXT")
    return conn


def _norm_iso(value):
    """Normalise ATS timestamps (ISO strings or epoch ms) to UTC ISO strings."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _job(row, company, source, fortune500):
    return {
        "id": str(row.get("id")),
        "company": company,
        "title": row["title"],
        "location": row["location"],
        "function": row["function"],
        "url": row["url"],
        "source": source,
        "fortune500": 1 if fortune500 else 0,
        "posted": _norm_iso(row.get("posted")),
    }


def fetch_greenhouse(slug: str, name: str, fortune500: bool):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    jobs = []
    for j in resp.json().get("jobs", [])[:MAX_JOBS_PER_COMPANY]:
        jobs.append(_job({
            "id": j.get("id"),
            "title": j.get("title") or "",
            "location": (j.get("location") or {}).get("name"),
            "function": ", ".join(d.get("name", "") for d in j.get("departments") or []),
            "url": j.get("absolute_url"),
            "posted": j.get("updated_at"),
        }, name, "greenhouse", fortune500))
    return jobs


def fetch_lever(slug: str, name: str, fortune500: bool):
    resp = requests.get(f"https://api.lever.co/v0/postings/{slug}", timeout=15)
    resp.raise_for_status()
    jobs = []
    for j in resp.json()[:MAX_JOBS_PER_COMPANY]:
        categories = j.get("categories") or {}
        jobs.append(_job({
            "id": j.get("id"),
            "title": j.get("text") or j.get("title"),
            "location": categories.get("location"),
            "function": categories.get("team") or categories.get("department"),
            "url": j.get("hostedUrl"),
            "posted": j.get("createdAt"),
        }, name, "lever", fortune500))
    return jobs


def fetch_ashby(slug: str, name: str, fortune500: bool):
    resp = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=15)
    resp.raise_for_status()
    jobs = []
    for j in resp.json().get("jobs", []):
        if not j.get("isListed", True):
            continue
        jobs.append(_job({
            "id": j.get("id"),
            "title": j.get("title"),
            "location": j.get("location"),
            "function": j.get("department"),
            "url": j.get("jobUrl"),
            "posted": j.get("publishedAt"),
        }, name, "ashby", fortune500))
        if len(jobs) == MAX_JOBS_PER_COMPANY:
            break
    return jobs


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def fetch_company(key: str, cfg: dict):
    fetch = FETCHERS.get(cfg.get("ats", ""))
    if not fetch:
        print(f"Unsupported ATS for {key}: {cfg.get('ats')}")
        return []
    try:
        jobs = fetch(cfg["slug"], cfg["name"], cfg.get("fortune500", False))
    except Exception as e:
        print(f"{cfg.get('ats')} error for {key}: {e}")
        return []
    for j in jobs:
        j["title"] = j["title"] or ""
        j["location"] = j["location"] or "Location not specified"
        j["function"] = j["function"] or ""
        j["url"] = j["url"] or ""
    return [j for j in jobs if j["title"] and j["url"]]


def sync(companies=None, path=None) -> dict:
    """Fetch every board and upsert into SQLite. Failed boards keep their old rows."""
    companies = COMPANIES if companies is None else companies
    conn = _connect(path or db_path())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda item: (item[0], fetch_company(*item)), companies.items()))

    for key, jobs in results:
        if not jobs:
            continue
        # Debug: ensure posted exists
        for j in jobs:
            if "posted" not in j:
                j["posted"] = ""
        conn.executemany("""
            INSERT INTO jobs (id, company, title, location, function, url, source, fortune500, posted, first_seen, last_seen)
            VALUES (:id, :company, :title, :location, :function, :url, :source, :fortune500, :posted, :now, :now)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title, location = excluded.location, function = excluded.function,
                url = excluded.url, source = excluded.source, fortune500 = excluded.fortune500,
                posted = excluded.posted, last_seen = excluded.last_seen
        """, [dict(j, now=now) for j in jobs])
        # Postings gone from the board are no longer listed.
        marks = ",".join("?" * len(jobs))
        conn.execute(f"DELETE FROM jobs WHERE company = ? AND id NOT IN ({marks})",
                     (companies[key]["name"], *[j["id"] for j in jobs]))

    conn.execute("INSERT INTO meta (key, value) VALUES ('last_sync', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (now,))
    conn.commit()
    conn.close()
    return counts()


def counts(path=None) -> dict:
    conn = _connect(path or db_path())
    total, companies = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT company) FROM jobs").fetchone()
    f500_jobs, f500_companies = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT company) FROM jobs WHERE fortune500 = 1").fetchone()
    by_source = dict(conn.execute(
        "SELECT source, COUNT(*) FROM jobs GROUP BY source").fetchall())
    by_company = [
        {"company": c, "jobs": n, "fortune500": bool(f)}
        for c, n, f in conn.execute(
            "SELECT company, COUNT(*), MAX(fortune500) FROM jobs "
            "GROUP BY company ORDER BY COUNT(*) DESC").fetchall()
    ]
    row = conn.execute("SELECT value FROM meta WHERE key = 'last_sync'").fetchone()
    conn.close()
    return {
        "total": total,
        "companies": companies,
        "fortune500_jobs": f500_jobs,
        "fortune500_companies": f500_companies,
        "by_source": by_source,
        "by_company": by_company,
        "last_sync": row[0] if row else None,
    }


def search_jobs(function="", location="", ids=None, path=None):
    sql = ("SELECT id, company, title, location, function, url, source, fortune500, posted "
           "FROM jobs")
    where, params = [], []
    if function:
        where.append("LOWER(function) LIKE ?")
        params.append(f"%{function.lower()}%")
    if location:
        where.append("LOWER(location) LIKE ?")
        params.append(f"%{location.lower()}%")
    if ids is not None:
        if not ids:
            return []
        where.append(f"id IN ({','.join('?' * len(ids))})")
        params.extend(ids)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY posted DESC, company, title"

    conn = _connect(path or db_path())
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [{
        "id": r[0], "company": r[1], "title": r[2], "location": r[3],
        "function": r[4], "url": r[5], "source": r[6], "fortune500": bool(r[7]),
        "posted": r[8],
    } for r in rows]


if __name__ == "__main__":
    print(f"Database: {db_path()}")
    c = sync()
    print(f"{c['total']} jobs from {c['companies']} companies "
          f"({c['fortune500_jobs']} Fortune 500) — sources: {c['by_source']}")
    for row in c["by_company"]:
        flag = "F500" if row["fortune500"] else "    "
        print(f"  {flag}  {row['company']:<12} {row['jobs']:>4}")
