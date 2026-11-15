"""Flask app for the Fortune 500 job board, backed by the local job store."""
import os
from urllib.parse import quote, urlencode

from flask import Flask, jsonify, render_template, request, session, Response

from . import sourcer

DEMO_JOBS = [
    {"id": "1", "title": "Senior Product Manager", "company": "Google",
     "location": "Bengaluru, India", "function": "Product",
     "url": "https://careers.google.com/roles/product-senior-product-manager",
     "source": "demo", "fortune500": False},
    {"id": "2", "title": "Software Engineer", "company": "Amazon",
     "location": "Seattle, WA", "function": "Engineering",
     "url": "https://careers.amazon.com/software-engineer",
     "source": "demo", "fortune500": False},
    {"id": "3", "title": "Product Designer", "company": "Microsoft",
     "location": "Bengaluru, India", "function": "Design",
     "url": "https://careers.microsoft.com/product-designer",
     "source": "demo", "fortune500": False},
    {"id": "4", "title": "Data Scientist", "company": "Swiggy",
     "location": "Bengaluru, India", "function": "Data",
     "url": "https://careers.swiggy.com/data-scientist",
     "source": "demo", "fortune500": False},
    {"id": "5", "title": "Backend Engineer", "company": "Razorpay",
     "location": "Bengaluru, India", "function": "Engineering",
     "url": "https://careers.razorpay.com/backend-engineer",
     "source": "demo", "fortune500": False},
    {"id": "6", "title": "Program Manager", "company": "Palantir",
     "location": "Bengaluru, India", "function": "Program Management",
     "url": "https://jobs.palantir.com/program-manager",
     "source": "demo", "fortune500": False},
    {"id": "7", "title": "Marketing Lead", "company": "Flipkart",
     "location": "Bengaluru, India", "function": "Marketing",
     "url": "https://careers.flipkart.com/marketing-lead",
     "source": "demo", "fortune500": False},
]

# ── Content & SEO data ─────────────────────────────────────────────────────
ROLE_SLUGS = {
    "software-engineer": "Software Engineer",
    "product-manager": "Product Manager",
    "data-scientist": "Data Scientist",
    "product-designer": "Product Designer",
    "backend-engineer": "Backend Engineer",
    "frontend-engineer": "Frontend Engineer",
    "devops-engineer": "DevOps Engineer",
    "program-manager": "Program Manager",
    "marketing-manager": "Marketing Manager",
    "sales-representative": "Sales Representative",
}

LOCATION_SLUGS = {
    "remote": "Remote",
    "san-francisco": "San Francisco, CA",
    "new-york": "New York, NY",
    "seattle": "Seattle, WA",
    "austin": "Austin, TX",
    "london": "London",
    "bengaluru": "Bengaluru, India",
    "dublin": "Dublin",
    "toronto": "Toronto",
}

BLOG_POSTS = [
    {
        "slug": "apply-direct-greenhouse-linkedin",
        "title": "How to Apply Directly on Greenhouse (and Why It Beats LinkedIn)",
        "description": "Skip the middleman. Here's why applying directly through Greenhouse, Lever, and Ashby gets your resume seen faster.",
        "date": "2026-11-10",
        "category": "Job Search Tips",
    },
    {
        "slug": "openai-jobs-application-tips",
        "title": "OpenAI Jobs: Where to Find Them and How to Stand Out",
        "description": "A complete guide to finding live OpenAI openings and making your application competitive.",
        "date": "2026-11-08",
        "category": "Company Guides",
    },
    {
        "slug": "stripe-careers-application-guide",
        "title": "Stripe Careers: Application Tips + Live Openings",
        "description": "Everything you need to know about applying to Stripe — engineering, product, design, and operations roles.",
        "date": "2026-11-05",
        "category": "Company Guides",
    },
    {
        "slug": "remote-jobs-top-tech-companies",
        "title": "Remote Jobs at Top Tech Companies — November 2026",
        "description": "The best remote openings at Airbnb, Stripe, OpenAI, Datadog, and more. Updated weekly.",
        "date": "2026-11-01",
        "category": "Remote Work",
    },
    {
        "slug": "why-aggregators-show-dead-listings",
        "title": "Why Job Aggregators Show Dead Listings (and How We Fix It)",
        "description": "That perfect role you found on a job board? It might have closed weeks ago. Here's what aggregators won't tell you.",
        "date": "2026-10-28",
        "category": "Job Search Tips",
    },
    {
        "slug": "coinbase-jobs-engineering-product-design",
        "title": "Coinbase Jobs: Engineering, Product & Design Roles",
        "description": "A complete guide to Coinbase careers — engineering, product, and design openings with insider application tips.",
        "date": "2026-11-12",
        "category": "Company Guides",
    },
    {
        "slug": "palantir-careers-what-they-look-for",
        "title": "Palantir Careers: What They Look For + How to Apply",
        "description": "Insider tips on Palantir's unique hiring process — Forward Deployed Engineer, engineering, and BD roles.",
        "date": "2026-11-09",
        "category": "Company Guides",
    },
    {
        "slug": "datadog-jobs-engineering-data-science",
        "title": "Datadog Jobs: Engineering & Data Science Openings",
        "description": "A guide to Datadog careers — engineering, data science, and SRE roles at the cloud monitoring leader.",
        "date": "2026-11-06",
        "category": "Company Guides",
    },
    {
        "slug": "best-companies-work-2026-live-openings",
        "title": "Best Companies to Work for in 2026 — Live Openings",
        "description": "The best tech companies to work for in 2026, ranked by culture, growth, and hiring volume.",
        "date": "2026-11-03",
        "category": "Career Guide",
    },
    {
        "slug": "track-job-applications-favorites-tool",
        "title": "How to Track Job Applications: Our Free Favorites Tool",
        "description": "Stop losing track of your job applications. Save roles, track status, and email yourself a shortlist.",
        "date": "2026-10-25",
        "category": "Job Search Tips",
    },
]


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
    app.config["AUTO_SYNC"] = os.environ.get("AUTO_SYNC", "1") == "1"

    def stats():
        return sourcer.counts()

    def ensure_synced():
        if app.config["AUTO_SYNC"] and not stats()["total"]:
            sourcer.sync()

    @app.route("/")
    def index():
        ensure_synced()
        return render_template("index.html",
                               favorites=session.get("favorites", []),
                               stats=stats())

    # ── SEO landing pages ────────────────────────────────────────────

    @app.route("/about")
    def about():
        return render_template("pages/about.html", stats=stats())

    @app.route("/sourcer")
    def sourcer_dashboard():
        ensure_synced()
        s = stats()
        # Build company data with direct links to their ATS boards
        companies_data = []
        for key, cfg in sourcer.COMPANIES.items():
            company_jobs = sourcer.search_jobs() if s["total"] else []
            company_jobs = [j for j in company_jobs if j["company"] == cfg["name"]]
            # Build ATS board URL
            if cfg["ats"] == "greenhouse":
                board_url = f"https://boards.greenhouse.io/{cfg['slug']}"
            elif cfg["ats"] == "lever":
                board_url = f"https://jobs.lever.co/{cfg['slug']}"
            elif cfg["ats"] == "ashby":
                board_url = f"https://jobs.ashbyhq.com/{cfg['slug']}"
            else:
                board_url = "#"
            companies_data.append({
                "key": key,
                "name": cfg["name"],
                "ats": cfg["ats"],
                "slug": cfg["slug"],
                "fortune500": cfg.get("fortune500", False),
                "job_count": len(company_jobs),
                "board_url": board_url,
            })
        # Sort by job count descending
        companies_data.sort(key=lambda x: x["job_count"], reverse=True)
        max_jobs = max((c["job_count"] for c in companies_data), default=1)
        return render_template("pages/sourcer.html",
                               stats=s,
                               companies=companies_data,
                               max_jobs=max_jobs)

    @app.route("/companies/<company_key>")
    def company_page(company_key):
        cfg = sourcer.COMPANIES.get(company_key)
        if not cfg:
            return render_template("pages/404.html", stats=stats()), 404
        ensure_synced()
        jobs = sourcer.search_jobs() if stats()["total"] else []
        jobs = [j for j in jobs if j["company"].lower() == cfg["name"].lower()]
        return render_template("pages/company.html",
                                 company=cfg,
                                 company_key=company_key,
                                 jobs=jobs,
                                 stats=stats())

    @app.route("/roles/<role_slug>")
    def role_page(role_slug):
        role_title = ROLE_SLUGS.get(role_slug)
        if not role_title:
            return render_template("pages/404.html", stats=stats()), 404
        ensure_synced()
        jobs = sourcer.search_jobs(function=role_title) if stats()["total"] else []
        return render_template("pages/role.html",
                               role=role_title,
                               role_slug=role_slug,
                               jobs=jobs,
                               stats=stats())

    @app.route("/locations/<loc_slug>")
    def location_page(loc_slug):
        location = LOCATION_SLUGS.get(loc_slug)
        if not location:
            return render_template("pages/404.html", stats=stats()), 404
        ensure_synced()
        jobs = sourcer.search_jobs(location=location) if stats()["total"] else []
        return render_template("pages/location.html",
                               location=location,
                               loc_slug=loc_slug,
                               jobs=jobs,
                               stats=stats())

    # ── Blog ─────────────────────────────────────────────────────────

    @app.route("/blog")
    def blog_index():
        return render_template("blog/index.html", posts=BLOG_POSTS, stats=stats())

    @app.route("/blog/<slug>")
    def blog_post(slug):
        post = next((p for p in BLOG_POSTS if p["slug"] == slug), None)
        if not post:
            return render_template("pages/404.html", stats=stats()), 404
        return render_template(f"blog/{slug}.html", post=post, posts=BLOG_POSTS, stats=stats())

    # ── SEO utilities ────────────────────────────────────────────────

    @app.route("/robots.txt")
    def robots():
        return Response("""User-agent: *
Allow: /
Sitemap: /sitemap.xml
""", mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap():
        base = request.url_root.rstrip("/")
        urls = [f"{base}/", f"{base}/about", f"{base}/blog"]

        for key in sourcer.COMPANIES:
            urls.append(f"{base}/companies/{key}")
        for slug in ROLE_SLUGS:
            urls.append(f"{base}/roles/{slug}")
        for slug in LOCATION_SLUGS:
            urls.append(f"{base}/locations/{slug}")
        for post in BLOG_POSTS:
            urls.append(f"{base}/blog/{post['slug']}")

        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for u in urls:
            xml += f"  <url><loc>{u}</loc></url>\n"
        xml += "</urlset>\n"
        return Response(xml, mimetype="application/xml")

    # ── Weekly Digest ───────────────────────────────────────────────

    @app.route("/weekly/<date_str>")
    def weekly_digest(date_str):
        """Show jobs first seen on a specific week."""
        ensure_synced()
        all_jobs = sourcer.search_jobs()
        # Filter jobs whose first_seen falls in the week starting date_str
        from datetime import datetime, timedelta
        try:
            week_start = datetime.strptime(date_str, "%Y-%m-%d")
            week_end = week_start + timedelta(days=7)
        except ValueError:
            return render_template("pages/404.html", stats=stats()), 404

        # Find jobs first seen this week
        week_jobs = []
        for job in all_jobs:
            if job.get("posted"):
                try:
                    posted = datetime.fromisoformat(job["posted"].replace("Z", "+00:00"))
                    if week_start <= posted < week_end:
                        week_jobs.append(job)
                except (ValueError, TypeError):
                    pass
            elif job.get("first_seen"):
                try:
                    first = datetime.fromisoformat(job["first_seen"].replace("Z", "+00:00"))
                    if week_start <= first < week_end:
                        week_jobs.append(job)
                except (ValueError, TypeError):
                    pass

        return render_template("pages/weekly.html",
                               date_str=date_str,
                               week_start=week_start.strftime("%B %d, %Y"),
                               week_end=week_end.strftime("%B %d, %Y"),
                               jobs=week_jobs,
                               stats=stats())

    # ── API routes (unchanged) ──────────────────────────────────────

    @app.route("/api/stats")
    def api_stats():
        return jsonify(stats())

    @app.route("/api/sync", methods=["POST"])
    def api_sync():
        sourcer.sync()
        return jsonify(stats())

    @app.route("/api/companies")
    def api_companies():
        return jsonify({"companies": sourcer.COMPANIES})

    @app.route("/api/jobs")
    def api_jobs():
        function_filter = request.args.get("function", "").strip()
        location_filter = request.args.get("location", "").strip()
        favorite_only = request.args.get("favorite", "false") == "true"
        use_demo = request.args.get("demo", "false") == "true"

        if use_demo:
            jobs = [j for j in DEMO_JOBS
                    if function_filter.lower() in j["function"].lower()
                    and location_filter.lower() in j["location"].lower()]
        else:
            ensure_synced()
            jobs = sourcer.search_jobs(function_filter, location_filter)

        if favorite_only:
            fav_set = set(session.get("favorites", []))
            jobs = [j for j in jobs if j["id"] in fav_set]

        return jsonify({
            "jobs": jobs,
            "count": len(jobs),
            "filters": {
                "function": function_filter,
                "location": location_filter,
                "favorite": favorite_only,
                "demo": use_demo,
            }
        })

    @app.route("/api/toggle-favorite", methods=["POST"])
    def toggle_favorite():
        job_id = str((request.get_json(silent=True) or {}).get("job_id") or "")
        if not job_id:
            return jsonify({"error": "job_id required"}), 400

        favorites = session.get("favorites", [])
        if job_id in favorites:
            favorites.remove(job_id)
            is_fav = False
        else:
            favorites.append(job_id)
            is_fav = True
        session["favorites"] = favorites

        return jsonify({"favorite": is_fav, "favorites": favorites})

    @app.route("/api/email-jobs", methods=["POST"])
    def email_jobs():
        data = request.get_json(silent=True) or {}
        job_ids = {str(i) for i in data.get("job_ids") or []}
        recipient = data.get("recipient") or ""

        if not job_ids:
            return jsonify({"error": "job_ids required"}), 400

        jobs = sourcer.search_jobs(ids=sorted(job_ids))
        jobs += [j for j in DEMO_JOBS if j["id"] in job_ids]

        subject = "Job Recommendations from Fortune 500 Companies"
        body = "\n".join(
            f"{j['title']} at {j['company']} - {j['location']} - {j['url']}"
            for j in jobs
        )
        query = urlencode({"subject": subject, "body": body}, quote_via=quote)
        return jsonify({"jobs": len(jobs), "mailto": f"mailto:{recipient}?{query}"})

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return render_template("pages/404.html", stats=stats()), 404

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001, debug=True)
