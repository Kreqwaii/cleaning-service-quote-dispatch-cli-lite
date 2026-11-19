import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import cleaning_dispatch as cd


class TestCleaningDispatch(unittest.TestCase):
    def test_standard_quote_basic(self):
        req = cd.QuoteRequest(area_sqm=100.0, cleaning_type="standard", bathrooms=1, windows=0)
        res = cd.calculate_quote(req)
        self.assertEqual(res.base_price, 160.0)
        self.assertEqual(res.extras_price, 22.0)
        self.assertEqual(res.total_price, 182.0)

    def test_minimum_price_enforced(self):
        req = cd.QuoteRequest(area_sqm=15.0, cleaning_type="standard", bathrooms=0, windows=0)
        res = cd.calculate_quote(req)
        self.assertEqual(res.base_price, 75.0)
        self.assertEqual(res.total_price, 75.0)

    def test_deep_cleaning_pricing(self):
        req = cd.QuoteRequest(area_sqm=80.0, cleaning_type="deep", bathrooms=2, windows=4)
        res = cd.calculate_quote(req)
        self.assertEqual(res.base_price, 228.0)
        self.assertEqual(res.extras_price, 2 * 22.0 + 4 * 9.5)
        self.assertEqual(res.total_price, 310.0)

    def test_post_renovation_pricing(self):
        req = cd.QuoteRequest(area_sqm=100.0, cleaning_type="post_renovation", bathrooms=1)
        res = cd.calculate_quote(req)
        self.assertEqual(res.base_price, 410.0)
        self.assertEqual(res.total_price, 432.0)

    def test_move_in_out_pricing(self):
        req = cd.QuoteRequest(area_sqm=100.0, cleaning_type="move_in_out", bathrooms=2)
        res = cd.calculate_quote(req)
        self.assertEqual(res.base_price, 340.0)
        self.assertEqual(res.total_price, 384.0)

    def test_office_cleaning_pricing(self):
        req = cd.QuoteRequest(area_sqm=200.0, cleaning_type="office", bathrooms=2, windows=10)
        res = cd.calculate_quote(req)
        self.assertEqual(res.base_price, 290.0)
        self.assertEqual(res.extras_price, 44.0 + 95.0)
        self.assertEqual(res.total_price, 429.0)

    def test_oven_and_fridge_extras(self):
        req = cd.QuoteRequest(
            area_sqm=60.0,
            cleaning_type="standard",
            bathrooms=1,
            include_oven=True,
            include_fridge=True,
        )
        res = cd.calculate_quote(req)
        self.assertEqual(res.extras_price, 22.0 + 28.0 + 24.0)

    def test_same_day_urgency_surcharge(self):
        req = cd.QuoteRequest(area_sqm=100.0, cleaning_type="standard", bathrooms=0, urgency="same_day")
        res = cd.calculate_quote(req)
        self.assertEqual(res.urgency_multiplier, 1.25)
        self.assertEqual(res.total_price, 200.0)

    def test_weekend_urgency_surcharge(self):
        req = cd.QuoteRequest(area_sqm=100.0, cleaning_type="standard", bathrooms=0, urgency="weekend")
        res = cd.calculate_quote(req)
        self.assertEqual(res.urgency_multiplier, 1.15)
        self.assertEqual(res.total_price, 184.0)

    def test_weekly_frequency_discount(self):
        req = cd.QuoteRequest(area_sqm=100.0, cleaning_type="standard", bathrooms=0, frequency="weekly")
        res = cd.calculate_quote(req)
        self.assertEqual(res.discount_rate, 0.15)
        self.assertEqual(res.total_price, 136.0)

    def test_biweekly_and_monthly_discounts(self):
        r_bi = cd.calculate_quote(
            cd.QuoteRequest(area_sqm=100.0, bathrooms=0, frequency="biweekly")
        )
        r_mo = cd.calculate_quote(
            cd.QuoteRequest(area_sqm=100.0, bathrooms=0, frequency="monthly")
        )
        self.assertEqual(r_bi.total_price, 144.0)
        self.assertEqual(r_mo.total_price, 152.0)

    def test_man_hours_and_crew_recommendation(self):
        req = cd.QuoteRequest(area_sqm=200.0, cleaning_type="post_renovation", bathrooms=3, windows=8)
        res = cd.calculate_quote(req)
        self.assertGreater(res.estimated_man_hours, 12.0)
        self.assertGreaterEqual(res.recommended_crew_size, 3)
        self.assertAlmostEqual(
            res.estimated_duration_hours,
            round(res.estimated_man_hours / res.recommended_crew_size, 2),
        )

    def test_invalid_area_raises(self):
        with self.assertRaises(ValueError):
            cd.calculate_quote(cd.QuoteRequest(area_sqm=0))

    def test_invalid_cleaning_type_raises(self):
        with self.assertRaises(ValueError):
            cd.calculate_quote(cd.QuoteRequest(area_sqm=50, cleaning_type="industrial"))

    def test_negative_bathrooms_or_windows_raises(self):
        with self.assertRaises(ValueError):
            cd.calculate_quote(cd.QuoteRequest(area_sqm=50, bathrooms=-1))
        with self.assertRaises(ValueError):
            cd.calculate_quote(cd.QuoteRequest(area_sqm=50, windows=-2))

    def test_invalid_urgency_or_frequency_raises(self):
        with self.assertRaises(ValueError):
            cd.calculate_quote(cd.QuoteRequest(area_sqm=50, urgency="express"))
        with self.assertRaises(ValueError):
            cd.calculate_quote(cd.QuoteRequest(area_sqm=50, frequency="daily"))

    def test_dispatch_crews_balances_load(self):
        quotes = [cd.calculate_quote(r) for r in cd.get_demo_requests()]
        assignments = cd.dispatch_crews(quotes, num_crews=2, max_hours_per_crew=20.0)
        self.assertEqual(len(assignments), 2)
        total_jobs = sum(len(a.jobs) for a in assignments)
        self.assertEqual(total_jobs, len(quotes))

    def test_dispatch_crews_same_zone_preference(self):
        q1 = cd.calculate_quote(cd.QuoteRequest(job_id="J1", zone="North", area_sqm=60))
        q2 = cd.calculate_quote(cd.QuoteRequest(job_id="J2", zone="North", area_sqm=60))
        assignments = cd.dispatch_crews([q1, q2], num_crews=2, max_hours_per_crew=10.0)
        north_crews = [a for a in assignments if "North" in a.zone]
        self.assertEqual(len(north_crews), 1)
        self.assertEqual(set(north_crews[0].jobs), {"J1", "J2"})

    def test_dispatch_invalid_params_raises(self):
        with self.assertRaises(ValueError):
            cd.dispatch_crews([], num_crews=0)
        with self.assertRaises(ValueError):
            cd.dispatch_crews([], num_crews=2, max_hours_per_crew=0)

    def test_export_quotes_csv(self):
        q = cd.calculate_quote(cd.QuoteRequest(area_sqm=75.0))
        csv_text = cd.export_quotes_csv([q])
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["job_id"], "JOB-001")

    def test_export_dispatch_csv(self):
        quotes = [cd.calculate_quote(r) for r in cd.get_demo_requests()]
        assignments = cd.dispatch_crews(quotes, num_crews=2)
        csv_text = cd.export_dispatch_csv(assignments)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 2)
        self.assertIn("CREW-01", rows[0]["crew_id"])

    def test_format_quotes_and_dispatch_text(self):
        quotes = [cd.calculate_quote(r) for r in cd.get_demo_requests()]
        q_text = cd.format_quotes_text(quotes)
        d_text = cd.format_dispatch_text(cd.dispatch_crews(quotes, num_crews=2))
        self.assertIn("JOB-101", q_text)
        self.assertIn("CREW DISPATCH SCHEDULE", d_text)

    def test_cli_quote_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cd.main(["quote", "--area", "100", "--type", "deep", "--format", "json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["cleaning_type"], "deep")
        self.assertGreater(data["total_price"], 0)

    def test_cli_quote_csv(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cd.main(["quote", "--area", "50", "--format", "csv"])
        self.assertEqual(rc, 0)
        self.assertIn("job_id,client_name", buf.getvalue())

    def test_cli_demo_text(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cd.main(["demo", "--crews", "2"])
        self.assertEqual(rc, 0)
        self.assertIn("CREW-01", buf.getvalue())

    def test_cli_demo_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cd.main(["demo", "--format", "json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("quotes", data)
        self.assertIn("dispatch", data)

    def test_cli_schedule_from_json_file(self):
        jobs = [
            {"job_id": "A1", "area_sqm": 80, "cleaning_type": "standard", "zone": "East"},
            {"job_id": "A2", "area_sqm": 110, "cleaning_type": "deep", "zone": "West"},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(jobs, tmp)
            tmp_path = tmp.name
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cd.main(["schedule", "--input", tmp_path, "--crews", "2", "--format", "json"])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(len(data["quotes"]), 2)
            self.assertEqual(len(data["dispatch"]), 2)
        finally:
            os.remove(tmp_path)

    def test_breakdown_keys_present(self):
        res = cd.calculate_quote(cd.QuoteRequest(area_sqm=90.0, include_oven=True))
        for key in ("area_base", "bathrooms", "windows", "oven", "fridge", "urgency_surcharge", "frequency_discount"):
            self.assertIn(key, res.breakdown)


if __name__ == "__main__":
    unittest.main()
