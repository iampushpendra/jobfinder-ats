"""Flask app for the Fortune 500 job board, backed by the local job store."""
import os
from urllib.parse import quote, urlencode

from flask import Flask, jsonify, render_template, request, session

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
        return jsonify({"error": "not found"}), 404

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001, debug=True)
