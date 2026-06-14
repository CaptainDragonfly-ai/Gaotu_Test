import os
import json
import re


STANDARD_ANSWER_PATH = "standard_answers.json"
STUDENT_ANSWER_PATH = "students_answers.json"
OUTPUT_DIR = "student_reports"


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_answer(answer):
    """
    统一答案格式：
    - 去空格
    - 转大写
    - 多选题按字母排序，例如 DBA -> ABD
    """
    if answer is None:
        return ""

    answer = str(answer).strip().upper()
    answer = re.sub(r"[^A-D]", "", answer)

    if len(answer) > 1:
        answer = "".join(sorted(set(answer)))

    return answer


def build_standard_answer_map(standard_answers):
    """
    把标准答案列表转成字典：
    {
        1: {"answer": "D", "analysis": "..."},
        2: {"answer": "B", "analysis": "..."}
    }
    """
    answer_map = {}

    for item in standard_answers:
        question_no = int(item["题号"])
        answer_map[question_no] = {
            "answer": normalize_answer(item.get("答案", "")),
            "analysis": item.get("解析", "")
        }

    return answer_map


def build_student_answer_map(student_answers):
    """
    把学生 answers 列表转成字典：
    {
        1: "C",
        2: "D"
    }
    """
    answer_map = {}

    for item in student_answers:
        question_no = int(item["题号"])
        answer_map[question_no] = normalize_answer(item.get("答案", ""))

    return answer_map


def safe_filename(text: str):
    """
    防止姓名、电话中出现非法文件名字符
    """
    text = str(text).strip()
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    return text or "unknown"


def compare_one_student(student, standard_map):
    student_answer_map = build_student_answer_map(student.get("answers", []))

    wrong_questions = []
    correct_count = 0
    wrong_count = 0
    blank_count = 0

    for question_no in sorted(standard_map.keys()):
        standard_answer = standard_map[question_no]["answer"]
        student_answer = student_answer_map.get(question_no, "")

        if not student_answer:
            blank_count += 1

        if student_answer == standard_answer:
            correct_count += 1
            continue

        wrong_count += 1

        wrong_questions.append({
            "题号": question_no,
            "学生答案": student_answer,
            "正确答案": standard_answer,
            "错误解析": standard_map[question_no]["analysis"]
        })

    total_questions = len(standard_map)

    report = {
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
            "正确率": round(correct_count / total_questions, 4) if total_questions else 0
        },
        "wrong_questions": wrong_questions
    }

    return report


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    standard_answers = load_json(STANDARD_ANSWER_PATH)
    students = load_json(STUDENT_ANSWER_PATH)

    standard_map = build_standard_answer_map(standard_answers)

    for student in students:
        report = compare_one_student(student, standard_map)

        name = safe_filename(student.get("name", "unknown"))
        phone = safe_filename(student.get("phone", "unknown"))
        page = student.get("page", "unknown")

        output_filename = f"{page}_{name}_{phone}.json"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"已生成：{output_path}")

    print("全部学生错题分析 JSON 已生成完成。")


if __name__ == "__main__":
    main()