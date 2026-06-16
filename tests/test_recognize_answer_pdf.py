import json
import tempfile
import unittest
from pathlib import Path

import fitz
import recognize_answer_pdf
from recognize_answer_pdf import parse_model_json, validate_and_normalize_result


class RecognizeAnswerPdfTests(unittest.TestCase):
    def test_parse_model_json_reads_json_inside_code_fence_with_extra_text(self):
        raw_content = '识别结果如下：\n```json\n{"answers": [{"题号": 1, "答案": "A"}]}\n```\n请查收。'

        parsed = parse_model_json(raw_content)

        self.assertEqual(parsed["answers"][0]["题号"], 1)

    def test_parse_model_json_reads_first_balanced_object(self):
        raw_content = '说明 {"answers": [{"题号": 1, "答案": "B"}]} 后续 {"ignored": true}'

        parsed = parse_model_json(raw_content)

        self.assertEqual(parsed["answers"][0]["答案"], "B")

    def test_validate_accepts_data_wrapper_and_answer_aliases(self):
        parsed = {
            "data": {
                "subject": "政治",
                "phone": "13800138000",
                "campus": "太原分校",
                "name": "张三",
                "answers": [
                    {"question_number": 1, "student_answer": "DBA"},
                    {"题目": 2, "作答": "C"},
                ],
            }
        }

        result = validate_and_normalize_result(parsed, page_num=1, min_answers=2)

        self.assertEqual(result["name"], "张三")
        self.assertEqual(result["answers"], [{"题号": 1, "答案": "ABD"}, {"题号": 2, "答案": "C"}])

    def test_validate_accepts_student_list_wrapper(self):
        parsed = {
            "students": [
                {
                    "name": "李四",
                    "answers": [
                        {"no": 1, "choice": "A"},
                        {"number": 2, "selected": "D"},
                    ],
                }
            ]
        }

        result = validate_and_normalize_result(parsed, page_num=1, min_answers=2)

        self.assertEqual(result["name"], "李四")
        self.assertEqual(result["answers"][1]["答案"], "D")

    def test_validate_rejects_payload_without_enough_answers(self):
        parsed = json.loads('{"answers": [{"题号": 1, "答案": "A"}]}')

        with self.assertRaises(ValueError):
            validate_and_normalize_result(parsed, page_num=1, min_answers=2)

    def test_recognize_pdf_answers_reports_page_progress(self):
        original_get_client = recognize_answer_pdf.get_client
        original_recognize_page = recognize_answer_pdf.recognize_page_with_retry

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "答题卡.pdf"
            doc = fitz.open()
            doc.new_page()
            doc.new_page()
            doc.save(pdf_path)
            doc.close()

            recognize_answer_pdf.get_client = lambda: object()
            recognize_answer_pdf.recognize_page_with_retry = lambda pdf_path, page_index, client: {
                "page": page_index + 1,
                "answers": [{"题号": 1, "答案": "A"}],
            }
            events = []

            try:
                results = recognize_answer_pdf.recognize_pdf_answers(
                    str(pdf_path),
                    show_progress=False,
                    progress_callback=lambda current, total: events.append((current, total)),
                )
            finally:
                recognize_answer_pdf.get_client = original_get_client
                recognize_answer_pdf.recognize_page_with_retry = original_recognize_page

        self.assertEqual(len(results), 2)
        self.assertEqual(events, [(0, 2), (1, 2), (2, 2)])


if __name__ == "__main__":
    unittest.main()
