import json
import shutil
import unittest

import app


class BranchReportListTests(unittest.TestCase):
    def test_load_delivery_reports_reads_storage_reports(self):
        report_dir = app.STORAGE_DIR / "_test_reports"
        shutil.rmtree(report_dir, ignore_errors=True)
        report_dir.mkdir(parents=True)
        report_path = report_dir / "1_张三_13800138000.json"
        report_path.write_text(
            json.dumps(
                {
                    "name": "张三",
                    "phone": "13800138000",
                    "subject": "政治",
                    "summary": {"总题数": 10, "正确题数": 8, "错误题数": 2, "空题数": 0, "正确率": 0.8},
                    "wrong_questions": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        try:
            reports = app.load_delivery_reports({"report_dir": app.relative_path(report_dir)})
        finally:
            shutil.rmtree(report_dir, ignore_errors=True)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["report"]["name"], "张三")
        self.assertTrue(reports[0]["report_path"].endswith("1_张三_13800138000.json"))


if __name__ == "__main__":
    unittest.main()
