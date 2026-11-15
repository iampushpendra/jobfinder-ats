"""Smoke tests — no network. Run with `python3 -m unittest test_app`."""
import os
import tempfile
import unittest

TMP = tempfile.mkdtemp()
os.environ["JOBS_DB"] = os.path.join(TMP, "test_jobs.db")
os.environ["AUTO_SYNC"] = "0"

from app import create_app, sourcer  # noqa: E402  (env must be set first)

FAKE_COMPANIES = {"fakeco": {"name": "FakeCo", "ats": "fake", "slug": "fakeco", "fortune500": True}}


def fake_posts(slug, name, fortune500):
    return [
        {"id": "101", "company": name, "title": "Staff Engineer", "location": "Remote",
         "function": "Engineering", "url": "https://boards.example/101",
         "source": "fake", "fortune500": bool(fortune500), "posted": ""},
        {"id": "102", "company": name, "title": "Product Designer", "location": "London",
         "function": "Design", "url": "https://boards.example/102",
         "source": "fake", "fortune500": bool(fortune500), "posted": ""},
    ]


def setUpModule():
    sourcer.FETCHERS["fake"] = fake_posts
    sourcer.sync(companies=FAKE_COMPANIES)


class SourcerTest(unittest.TestCase):
    def test_counts(self):
        c = sourcer.counts()
        self.assertEqual(c["total"], 2)
        self.assertEqual(c["companies"], 1)
        self.assertEqual(c["fortune500_jobs"], 2)
        self.assertEqual(c["fortune500_companies"], 1)
        self.assertEqual(c["by_source"], {"fake": 2})
        self.assertTrue(c["last_sync"])

    def test_search_filters(self):
        self.assertEqual([j["id"] for j in sourcer.search_jobs("engineer")], ["101"])
        self.assertEqual([j["id"] for j in sourcer.search_jobs("", "london")], ["102"])
        self.assertEqual(sourcer.search_jobs("", "mars"), [])
        self.assertEqual([j["id"] for j in sourcer.search_jobs(ids=["102"])], ["102"])

    def test_sync_prunes_jobs_gone_from_board(self):
        other = os.path.join(TMP, "other.db")
        sourcer.sync(companies=FAKE_COMPANIES, path=other)
        self.assertEqual(sourcer.counts(other)["total"], 2)

        sourcer.FETCHERS["fake"] = lambda slug, name, f: [{
            "id": "101", "company": name, "title": "Staff Engineer", "location": "Remote",
            "function": "Engineering", "url": "https://boards.example/101",
            "source": "fake", "fortune500": True}]
        sourcer.sync(companies=FAKE_COMPANIES, path=other)
        self.assertEqual(sourcer.counts(other)["total"], 1)


class AppTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_index_renders(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("let favorites = [];", body)
        self.assertIn("Fortune 500 roles", body)

    def test_static_css_is_served(self):
        self.assertEqual(self.client.get("/static/style.css").status_code, 200)

    def test_jobs_come_from_store(self):
        data = self.client.get("/api/jobs").get_json()
        self.assertEqual(data["count"], 2)
        self.assertTrue(all(j["url"].startswith("https://") for j in data["jobs"]))
        self.assertEqual(self.client.get("/api/jobs?function=design").get_json()["count"], 1)

    def test_demo_jobs_still_work(self):
        self.assertEqual(self.client.get("/api/jobs?demo=true").get_json()["count"], 7)

    def test_toggle_favorite_and_filter(self):
        first = self.client.post("/api/toggle-favorite", json={"job_id": 101}).get_json()
        self.assertEqual(first["favorite"], True)
        self.assertEqual(first["favorites"], ["101"])
        self.assertEqual(self.client.get("/api/jobs?favorite=true").get_json()["count"], 1)

        second = self.client.post("/api/toggle-favorite", json={"job_id": "101"}).get_json()
        self.assertEqual(second["favorite"], False)
        self.assertEqual(second["favorites"], [])

    def test_email_links_to_job_ids(self):
        self.client.post("/api/toggle-favorite", json={"job_id": "101"})
        data = self.client.post("/api/email-jobs", json={"job_ids": ["101"]}).get_json()
        self.assertEqual(data["jobs"], 1)
        self.assertTrue(data["mailto"].startswith("mailto:?subject=Job%20Recommendations"))
        self.assertIn("https://boards.example/101", data["mailto"].replace("%3A", ":").replace("%2F", "/"))

    def test_stats_endpoint(self):
        s = self.client.get("/api/stats").get_json()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["fortune500_jobs"], 2)

    def test_about_page(self):
        body = self.client.get("/about").get_data(as_text=True)
        self.assertIn("We source live job openings", body)
        self.assertEqual(self.client.get("/about").status_code, 200)

    def test_blog_index(self):
        body = self.client.get("/blog").get_data(as_text=True)
        self.assertIn("Job Search Tips", body)
        self.assertIn("Company Guides", body)

    def test_blog_post(self):
        body = self.client.get("/blog/apply-direct-greenhouse-linkedin").get_data(as_text=True)
        self.assertIn("Greenhouse", body)
        self.assertIn("LinkedIn", body)

    def test_company_page(self):
        body = self.client.get("/companies/stripe").get_data(as_text=True)
        self.assertIn("Stripe Jobs", body)
        self.assertIn("greenhouse", body)

    def test_role_page(self):
        body = self.client.get("/roles/software-engineer").get_data(as_text=True)
        self.assertIn("Software Engineer", body)

    def test_location_page(self):
        body = self.client.get("/locations/remote").get_data(as_text=True)
        self.assertIn("Remote", body)

    def test_sitemap(self):
        body = self.client.get("/sitemap.xml").get_data(as_text=True)
        self.assertIn("<urlset", body)
        self.assertIn("/blog/apply-direct-greenhouse-linkedin", body)

    def test_robots_txt(self):
        body = self.client.get("/robots.txt").get_data(as_text=True)
        self.assertIn("Sitemap:", body)


if __name__ == "__main__":
    unittest.main()
