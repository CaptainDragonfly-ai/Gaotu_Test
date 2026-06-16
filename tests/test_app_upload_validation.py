import unittest

from app import require_pdf


class FakeUpload:
    def __init__(self, filename):
        self.filename = filename


class UploadValidationTests(unittest.TestCase):
    def test_require_pdf_accepts_english_pdf_names(self):
        self.assertTrue(require_pdf(FakeUpload("student.pdf")))
        self.assertTrue(require_pdf(FakeUpload("student.PDF")))

    def test_require_pdf_accepts_chinese_pdf_names(self):
        self.assertTrue(require_pdf(FakeUpload("答题卡.pdf")))
        self.assertTrue(require_pdf(FakeUpload("学生答案.PDF")))

    def test_require_pdf_rejects_non_pdf_or_empty_names(self):
        self.assertFalse(require_pdf(FakeUpload("答题卡.docx")))
        self.assertFalse(require_pdf(FakeUpload("")))
        self.assertFalse(require_pdf(FakeUpload(None)))


if __name__ == "__main__":
    unittest.main()
