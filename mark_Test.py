import json
import os
import re
from pathlib import Path


STANDARD_ANSWER_PATH = "standard_answers.json"
STUDENT_ANSWER_PATH = "students_answers.json"
OUTPUT_DIR = "student_reports"


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_value(data: dict, *keys, default=""):
    """兼容新旧字段名；输入字典和候选键，输出第一个存在的值。"""
    for key in keys:
        if key in data:
            return data.get(key)
    return default


def normalize_answer(answer):
    """
    统一答案格式；输入任意答案文本，输出只包含 A-D 且排序后的答案。
    这样 DBA 和 ABD 会被视为同一个多选答案。
    """
    if answer is None:
        return ""

    answer = str(answer).strip().upper()
    answer = re.sub(r"[^A-D]", "", answer)

    if len(answer) > 1:
        answer = "".join(sorted(set(answer)))

    return answer


def build_standard_answer_map(standard_answers):
    """把标准答案列表转为题号索引字典；输入标准答案列表，输出便于批改的映射。"""
    answer_map = {}

    for item in standard_answers:
        question_no = int(pick_value(item, "题号", "棰樺彿"))
        answer_map[question_no] = {
            "answer": normalize_answer(pick_value(item, "答案", "绛旀")),
            "analysis": pick_value(item, "解析", "瑙ｆ瀽"),
        }

    return answer_map


def build_student_answer_map(student_answers):
    """把学生 answers 列表转为题号索引字典；输入作答列表，输出题号到答案的映射。"""
    answer_map = {}

    for item in student_answers:
        question_no = int(pick_value(item, "题号", "棰樺彿"))
        answer_map[question_no] = normalize_answer(pick_value(item, "答案", "绛旀"))

    return answer_map


def safe_filename(text: str):
    """清理文件名中的非法字符；输入姓名或电话，输出安全文件名片段。"""
    text = str(text).strip()
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    return text or "unknown"


def compare_one_student(student, standard_map):
    """批改单个学生；输入学生作答和标准答案映射，输出成绩报告。"""
    student_answer_map = build_student_answer_map(student.get("answers", []))
    wrong_questions = []
    correct_count = 0
    blank_count = 0

    for question_no in sorted(standard_map.keys()):
        standard_answer = standard_map[question_no]["answer"]
        student_answer = student_answer_map.get(question_no, "")

        if not student_answer:
            blank_count += 1

        if student_answer == standard_answer:
            correct_count += 1
            continue

        wrong_questions.append(
            {
                "题号": question_no,
                "学生答案": student_answer,
                "正确答案": standard_answer,
                "错误解析": standard_map[question_no]["analysis"],
            }
        )

    total_questions = len(standard_map)
    wrong_count = len(wrong_questions)

    return {
        "page": student.get("page"),
        "subject": student.get("subject"),
        "phone": student.get("phone"),
        "campus": student.get("campus"),
        "name": student.get("name"),
        "summary": {
            "总题数": total_questions,
            "正确题数": correct_count,
            "错误题数": wrong_count,
            "空题数": blank_count,
            "正确率": round(correct_count / total_questions, 4) if total_questions else 0,
        },
        "wrong_questions": wrong_questions,
    }


def grade_students(standard_answers, students):
    """批改一批学生；输入标准答案和学生作答列表，输出学生报告列表。"""
    standard_map = build_standard_answer_map(standard_answers)
    return [compare_one_student(student, standard_map) for student in students]


def save_reports(reports, output_dir: str):
    """保存批改报告；输入报告列表和目录，输出每个报告的文件路径。"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for report in reports:
        name = safe_filename(report.get("name", "unknown"))
        phone = safe_filename(report.get("phone", "unknown"))
        page = report.get("page", "unknown")
        output_path = os.path.join(output_dir, f"{page}_{name}_{phone}.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        saved_paths.append(output_path)

    return saved_paths


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    reports = grade_students(load_json(STANDARD_ANSWER_PATH), load_json(STUDENT_ANSWER_PATH))
    save_reports(reports, OUTPUT_DIR)
    print("全部学生错题分析 JSON 已生成完成。")


if __name__ == "__main__":
    main()
