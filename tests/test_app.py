import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SUBSCHECK_DB"] = _tmp.name

import app as app_module  # noqa: E402


class SubsCheckTest(unittest.TestCase):
    def setUp(self):
        app_module.init_db()
        self.client = app_module.app.test_client()
        with app_module.app.app_context():
            conn = app_module.get_db()
            conn.execute("DELETE FROM subs")
            conn.commit()

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_index_ok(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("サブスク棚卸しメモ", res.get_data(as_text=True))

    def test_total_calculation(self):
        self.client.post("/add", data={"name": "音楽配信", "amount": "980",
                                       "billing_day": "10", "review_date": "", "memo": ""})
        self.client.post("/add", data={"name": "動画配信", "amount": "1490",
                                       "billing_day": "25", "review_date": "2027-01-01", "memo": "見直す"})
        with app_module.app.app_context():
            conn = app_module.get_db()
            total = app_module.monthly_total(conn)
        self.assertEqual(total, 2470)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("2470 円", body)          # 月額合計
        self.assertIn("29640 円", body)         # 年間換算 = 2470 * 12
        self.assertIn("音楽配信", body)
        self.assertIn("動画配信", body)

    def test_add_visible_delete_gone(self):
        self.client.post("/add", data={"name": "クラウド保存", "amount": "300",
                                       "billing_day": "1", "review_date": "", "memo": ""})
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("クラウド保存", body)
        with app_module.app.app_context():
            conn = app_module.get_db()
            sid = conn.execute("SELECT id FROM subs").fetchone()["id"]
        res = self.client.post(f"/delete/{sid}")
        self.assertEqual(res.status_code, 302)
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("クラウド保存", body)
        self.assertIn("0 円", body)

    def test_invalid_billing_day_rejected(self):
        self.client.post("/add", data={"name": "だめな登録", "amount": "100",
                                       "billing_day": "32", "review_date": "", "memo": ""})
        with app_module.app.app_context():
            conn = app_module.get_db()
            n = conn.execute("SELECT COUNT(*) AS c FROM subs").fetchone()["c"]
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
