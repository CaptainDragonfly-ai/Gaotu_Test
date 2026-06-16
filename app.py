import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from mark_Test import grade_students, save_reports
from recognize_answer_pdf import recognize_pdf_answers
from standard_answers import parse_standard_pdf, save_to_json


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
DB_PATH = DATA_DIR / "app_data.json"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def init_runtime_dirs():
    """初始化运行目录；输入为空，输出为空，保证数据和文件目录存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        save_db({"campuses": [], "exams": [], "deliveries": {}})


def load_db():
    """读取本地 JSON 数据库；输入为空，输出系统元数据字典。"""
    init_runtime_dirs()
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    """保存本地 JSON 数据库；输入元数据字典，输出为空。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def campus_map(db):
    return {campus["id"]: campus for campus in db["campuses"]}


def find_exam(db, exam_id):
    return next((exam for exam in db["exams"] if exam["id"] == exam_id), None)


def find_campus(db, campus_id):
    return next((campus for campus in db["campuses"] if campus["id"] == campus_id), None)


def delivery_key(exam_id, campus_id):
    return f"{exam_id}:{campus_id}"


def save_upload(file_storage, target_path: Path):
    """保存上传文件；输入 Flask 文件对象和目标路径，输出保存后的路径。"""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(target_path)
    return target_path


def require_pdf(file_storage):
    filename = secure_filename(file_storage.filename or "")
    return filename.lower().endswith(".pdf")


def relative_path(path: Path):
    return path.resolve().relative_to(BASE_DIR).as_posix()


def absolute_path(path_text: str):
    return BASE_DIR / path_text


def storage_file_exists(path_text: str):
    if not path_text:
        return False

    path = absolute_path(path_text)
    return path.exists() and path.resolve().is_relative_to(STORAGE_DIR.resolve())


def ensure_delivery_sets(delivery, exam):
    """补齐可选答案列表；输入交付记录和试卷记录，输出标准答案与学生答案选项。"""
    standard_sets = delivery.setdefault("standard_answer_sets", [])
    student_sets = delivery.setdefault("student_answer_sets", [])

    if not standard_sets and delivery.get("standard_json_path"):
        standard_sets.append(
            {
                "id": "default",
                "name": "总校下发标准答案",
                "json_path": delivery["standard_json_path"],
                "pdf_path": delivery.get("standard_pdf_path") or exam.get("standard_pdf_path", ""),
                "created_at": delivery.get("updated_at") or now_text(),
            }
        )

    if not student_sets and delivery.get("student_json_path"):
        student_sets.append(
            {
                "id": "default",
                "name": "已识别学生答案",
                "json_path": delivery["student_json_path"],
                "pdf_path": delivery.get("student_pdf_path", ""),
                "created_at": delivery.get("updated_at") or now_text(),
            }
        )

    return standard_sets, student_sets


def find_answer_set(answer_sets, set_id):
    return next((item for item in answer_sets if item["id"] == set_id), None)


@app.context_processor
def inject_globals():
    return {"now_text": now_text}


@app.route("/")
def index():
    return redirect(url_for("headquarters"))


@app.route("/headquarters", methods=["GET", "POST"])
def headquarters():
    db = load_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        recipient_ids = request.form.getlist("campus_ids")
        paper = request.files.get("paper_pdf")
        standard = request.files.get("standard_pdf")

        if (
            not title
            or not subject
            or not recipient_ids
            or not paper
            or not standard
            or not require_pdf(paper)
            or not require_pdf(standard)
        ):
            flash("请填写试卷信息、选择分校，并同时上传试卷 PDF 和答案 PDF。", "error")
            return redirect(url_for("headquarters"))

        exam_id = uuid4().hex[:12]
        exam_dir = STORAGE_DIR / "exams" / exam_id
        paper_path = save_upload(paper, exam_dir / "paper.pdf")
        standard_path = save_upload(standard, exam_dir / "standard_answer.pdf")
        standard_json_path = exam_dir / "results" / "standard" / "standard_answers.json"
        standard_answers = parse_standard_pdf(str(standard_path))
        save_to_json(standard_answers, str(standard_json_path))

        exam = {
            "id": exam_id,
            "title": title,
            "subject": subject,
            "paper_path": relative_path(paper_path),
            "standard_pdf_path": relative_path(standard_path),
            "standard_json_path": relative_path(standard_json_path),
            "recipients": recipient_ids,
            "created_at": now_text(),
        }
        db["exams"].insert(0, exam)

        # 标准答案由总校随试卷成套下发，分校只需要上传学生答题卡并发起批改。
        for campus_id in recipient_ids:
            key = delivery_key(exam_id, campus_id)
            db["deliveries"][key] = {
                "exam_id": exam_id,
                "campus_id": campus_id,
                "student_pdf_path": "",
                "standard_pdf_path": exam["standard_pdf_path"],
                "student_json_path": "",
                "standard_json_path": exam["standard_json_path"],
                "standard_answer_sets": [
                    {
                        "id": "default",
                        "name": "总校下发标准答案",
                        "json_path": exam["standard_json_path"],
                        "pdf_path": exam["standard_pdf_path"],
                        "created_at": now_text(),
                    }
                ],
                "student_answer_sets": [],
                "report_dir": "",
                "report_count": 0,
                "status": "已下发",
                "updated_at": now_text(),
            }

        save_db(db)
        flash("试卷和答案已成套下发到指定分校。", "success")
        return redirect(url_for("headquarters"))

    return render_template("headquarters.html", db=db, campuses=campus_map(db))


@app.route("/campuses", methods=["POST"])
def create_campus():
    db = load_db()
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip()

    if not name or not code:
        flash("分校名称和编码不能为空。", "error")
        return redirect(url_for("headquarters"))

    if any(campus["code"] == code for campus in db["campuses"]):
        flash("分校编码已存在。", "error")
        return redirect(url_for("headquarters"))

    db["campuses"].append({"id": uuid4().hex[:8], "name": name, "code": code})
    save_db(db)
    flash("分校已注册。", "success")
    return redirect(url_for("headquarters"))


@app.route("/campuses/<campus_id>/delete", methods=["POST"])
def delete_campus(campus_id):
    db = load_db()
    campus = find_campus(db, campus_id)

    if not campus:
        flash("分校不存在。", "error")
        return redirect(url_for("headquarters"))

    db["campuses"] = [item for item in db["campuses"] if item["id"] != campus_id]

    # 删除分校时，只移除该分校的接收关系和交付记录，不删除已经上传的试卷原件。
    for exam in db["exams"]:
        exam["recipients"] = [item for item in exam.get("recipients", []) if item != campus_id]

    db["deliveries"] = {
        key: value for key, value in db["deliveries"].items() if value.get("campus_id") != campus_id
    }

    save_db(db)
    flash(f"已删除分校：{campus['name']}。", "success")
    return redirect(url_for("headquarters"))


@app.route("/branch")
def branch():
    db = load_db()
    selected_id = request.args.get("campus_id") or (db["campuses"][0]["id"] if db["campuses"] else "")
    selected = find_campus(db, selected_id)
    exams = []

    if selected:
        for exam in db["exams"]:
            if selected_id in exam.get("recipients", []):
                delivery = db["deliveries"].get(delivery_key(exam["id"], selected_id), {})
                exams.append({"exam": exam, "delivery": delivery})

    return render_template("branch.html", db=db, selected=selected, exams=exams)


@app.route("/branch/<campus_id>/exam/<exam_id>", methods=["GET", "POST"])
def branch_exam(campus_id, exam_id):
    db = load_db()
    exam = find_exam(db, exam_id)
    campus = find_campus(db, campus_id)
    key = delivery_key(exam_id, campus_id)
    delivery = db["deliveries"].get(key)

    if not exam or not campus or not delivery:
        flash("未找到该分校的试卷记录。", "error")
        return redirect(url_for("branch"))

    # 兼容旧数据：如果历史交付记录缺答案路径，则从试卷记录补齐。
    if not delivery.get("standard_json_path") and exam.get("standard_json_path"):
        delivery["standard_pdf_path"] = exam.get("standard_pdf_path", "")
        delivery["standard_json_path"] = exam.get("standard_json_path", "")

    standard_sets, student_sets = ensure_delivery_sets(delivery, exam)

    if request.method == "POST":
        action = request.form.get("action")
        exam_dir = STORAGE_DIR / "exams" / exam_id
        delivery_dir = STORAGE_DIR / "exams" / exam_id / "campuses" / campus_id

        try:
            if action == "upload_students":
                student_pdf = request.files.get("student_pdf")
                if not student_pdf or not require_pdf(student_pdf):
                    raise ValueError("请上传学生答题卡 PDF。")

                set_id = uuid4().hex[:8]
                pdf_path = save_upload(student_pdf, delivery_dir / f"student_answers_{set_id}.pdf")
                students = recognize_pdf_answers(str(pdf_path))
                json_path = exam_dir / "results" / "students" / campus_id / f"students_answers_{set_id}.json"
                save_to_json(students, str(json_path))

                delivery["student_pdf_path"] = relative_path(pdf_path)
                delivery["student_json_path"] = relative_path(json_path)
                student_sets.append(
                    {
                        "id": set_id,
                        "name": f"学生答案 {now_text()}",
                        "json_path": delivery["student_json_path"],
                        "pdf_path": delivery["student_pdf_path"],
                        "created_at": now_text(),
                    }
                )
                delivery["status"] = "已识别答题卡"

            elif action == "grade":
                standard_set_id = request.form.get("standard_set_id", "")
                student_set_id = request.form.get("student_set_id", "")
                standard_set = find_answer_set(standard_sets, standard_set_id)
                student_set = find_answer_set(student_sets, student_set_id)

                if not standard_set or not student_set:
                    raise ValueError("请选择标准答案和学生答案后再批改。")

                standard_answers = json.loads(absolute_path(standard_set["json_path"]).read_text(encoding="utf-8"))
                students = json.loads(absolute_path(student_set["json_path"]).read_text(encoding="utf-8"))
                reports = grade_students(standard_answers, students)
                report_dir = exam_dir / "results" / "reports" / campus_id / f"{standard_set_id}_{student_set_id}"

                if report_dir.exists():
                    shutil.rmtree(report_dir)

                save_reports(reports, str(report_dir))
                delivery["report_dir"] = relative_path(report_dir)
                delivery["report_count"] = len(reports)
                delivery["selected_standard_set_id"] = standard_set_id
                delivery["selected_student_set_id"] = student_set_id
                delivery["status"] = "已批改"

            else:
                raise ValueError("未知操作。")

            delivery["updated_at"] = now_text()
            db["deliveries"][key] = delivery
            save_db(db)
            flash("操作完成。", "success")

        except Exception as exc:
            flash(f"处理失败：{exc}", "error")

        return redirect(url_for("branch_exam", campus_id=campus_id, exam_id=exam_id))

    return render_template(
        "branch_exam.html",
        exam=exam,
        campus=campus,
        delivery=delivery,
        standard_sets=standard_sets,
        student_sets=student_sets,
    )


@app.route("/student", methods=["GET", "POST"])
def student():
    db = load_db()
    results = []
    filters = {"campus_id": "", "name": "", "phone": ""}

    if request.method == "POST":
        filters = {
            "campus_id": request.form.get("campus_id", "").strip(),
            "name": request.form.get("name", "").strip(),
            "phone": request.form.get("phone", "").strip(),
        }

        for delivery in db["deliveries"].values():
            if delivery.get("campus_id") != filters["campus_id"] or not delivery.get("report_dir"):
                continue

            exam = find_exam(db, delivery["exam_id"])
            campus = find_campus(db, delivery["campus_id"])
            report_dir = absolute_path(delivery["report_dir"])

            for report_path in report_dir.glob("*.json"):
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if report.get("name") == filters["name"] and report.get("phone") == filters["phone"]:
                    results.append(
                        {
                            "exam": exam,
                            "campus": campus,
                            "delivery": delivery,
                            "report": report,
                            "report_path": relative_path(report_path),
                        }
                    )

    return render_template("student.html", db=db, filters=filters, results=results)


@app.route("/student/report")
def student_report():
    report_path = request.args.get("path", "")

    if not storage_file_exists(report_path):
        flash("未找到成绩报告。", "error")
        return redirect(url_for("student"))

    report = json.loads(absolute_path(report_path).read_text(encoding="utf-8"))
    return render_template("student_report.html", report=report)


@app.route("/files/preview")
def preview_file():
    path_text = request.args.get("path", "")

    if not storage_file_exists(path_text):
        return "文件不存在", 404

    return send_file(absolute_path(path_text), mimetype="application/pdf", as_attachment=False)


@app.route("/files/download")
def download_file():
    path_text = request.args.get("path", "")

    if not storage_file_exists(path_text):
        return "文件不存在", 404

    path = absolute_path(path_text)
    return send_file(path, as_attachment=True, download_name=path.name)


if __name__ == "__main__":
    init_runtime_dirs()
    app.run(host="127.0.0.1", port=5000, debug=True)
