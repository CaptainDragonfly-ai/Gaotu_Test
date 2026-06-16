import base64
import io
import json
import os
import re
from pathlib import Path

import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


load_dotenv()

PDF_PATH = r"D:\desktop\高途面试\题目\试卷\答卷.pdf"
OUTPUT_JSON = "results/students/students_answers.json"
EXPECTED_ANSWER_COUNT = 33
MIN_ACCEPTED_ANSWER_COUNT = 20
MAX_COMPLETION_TOKENS = 4096
API_CALL_RETRIES = 3

QUESTION_KEY = "题号"
ANSWER_KEY = "答案"
QUESTION_KEYS = (QUESTION_KEY, "question_no", "question", "no")
ANSWER_KEYS = (ANSWER_KEY, "answer")

IMAGE_PROFILES = [
    {"name": "standard", "dpi": 300, "contrast": 1.8, "sharpness": 1.4},
    {"name": "retry", "dpi": 360, "contrast": 2.2, "sharpness": 1.8},
]


def format_progress(current: int, total: int, width: int = 30):
    """格式化识别进度条；输入当前数量和总数，输出命令行可显示的进度文本。"""
    if total <= 0:
        return "[{}] 0/0 100.0%".format("#" * width)

    current = max(0, min(current, total))
    percent = current / total
    filled = int(width * percent)
    bar = "#" * filled + "." * (width - filled)
    return f"[{bar}] {current}/{total} {percent * 100:5.1f}%"


def print_progress(current: int, total: int):
    """打印识别进度；输入当前页数和总页数，输出单行刷新的进度条。"""
    print(f"\r识别进度 {format_progress(current, total)}", end="", flush=True)
    if current >= total:
        print()


def get_client():
    """创建 MiMo API 客户端；输入为空，输出 OpenAI 兼容客户端。"""
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise ValueError("未配置 MIMO_API_KEY，无法识别学生答题卡。")

    return OpenAI(
        api_key=api_key,
        base_url="https://api.xiaomimimo.com/v1",
        timeout=30,
        max_retries=1,
    )


def parse_model_json(content: str):
    """解析模型返回的 JSON；输入模型文本，输出字典，兼容 Markdown 代码块。"""
    if not content:
        raise ValueError("模型返回内容为空。")

    candidates = [content.strip()]

    # MiMo 有时会把 JSON 包在 ```json 代码块里，先剥掉外层再解析。
    code_block = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidates[0], flags=re.DOTALL | re.IGNORECASE)
    if code_block:
        candidates.append(code_block.group(1).strip())

    # 如果模型额外输出说明文字，尽量提取第一个 JSON 对象，避免误判整页失败。
    json_object = re.search(r"\{.*\}", candidates[0], flags=re.DOTALL)
    if json_object:
        candidates.append(json_object.group(0).strip())

    last_error = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    raise ValueError(f"模型返回内容不是合法 JSON：{last_error}")


def pick_value(data: dict, keys, default=""):
    """从多个候选字段中取值；输入字典和字段名列表，输出第一个存在的值。"""
    for key in keys:
        if key in data:
            return data.get(key)
    return default


def normalize_answer(answer):
    """规范化答案；输入任意文本，输出只包含 A-D 且去重排序后的答案。"""
    if answer is None:
        return ""

    cleaned = re.sub(r"[^A-D]", "", str(answer).upper())
    if len(cleaned) > 1:
        return "".join(sorted(set(cleaned)))
    return cleaned


def enhance_png_bytes(image_bytes: bytes, contrast: float = 1.8, sharpness: float = 1.4):
    """增强页面图片；输入 PNG 字节和增强参数，输出更适合视觉模型识别的 PNG 字节。"""
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(contrast)
    image = ImageEnhance.Sharpness(image).enhance(sharpness)
    image = image.filter(ImageFilter.SHARPEN)

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def pdf_page_to_base64_image(pdf_path: str, page_index: int, dpi: int = 300, contrast: float = 1.8, sharpness: float = 1.4):
    """把 PDF 单页转成增强后的 base64 图片；输入页索引和增强参数，输出页面图片。"""
    doc = fitz.open(pdf_path)

    try:
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        image_bytes = enhance_png_bytes(pix.tobytes("png"), contrast=contrast, sharpness=sharpness)

        return {
            "page": page_index + 1,
            "base64": base64.b64encode(image_bytes).decode("utf-8"),
        }
    finally:
        doc.close()


def pdf_page_to_base64_images(pdf_path: str, dpi: int = 300, contrast: float = 1.8, sharpness: float = 1.4):
    """把 PDF 每页转成增强后的 base64 图片；输入 PDF 路径和增强参数，输出页面图片列表。"""
    doc = fitz.open(pdf_path)

    try:
        page_count = len(doc)
    finally:
        doc.close()

    return [
        pdf_page_to_base64_image(pdf_path, page_index, dpi=dpi, contrast=contrast, sharpness=sharpness)
        for page_index in range(page_count)
    ]


def build_prompt(page_num: int):
    """生成识别提示词；输入页码，输出要求模型稳定返回 JSON 的提示词。"""
    return f"""
你是一个答题卡 OCR 识别助手。请识别图片中的学生答题卡，并且只输出合法 JSON，不要输出解释、Markdown 或额外文字。

必须返回以下结构：
{{
  "page": {page_num},
  "subject": "科目",
  "phone": "手机号",
  "campus": "校区",
  "name": "姓名",
  "answers": [
    {{
      "题号": 1,
      "答案": "A"
    }}
  ]
}}

识别规则：
1. 科目通常在右上角，例如“科目：政治”。
2. 手机号、校区、姓名通常在表格上方。
3. 客观题通常有 {EXPECTED_ANSWER_COUNT} 题，请尽量按题号从 1 到 {EXPECTED_ANSWER_COUNT} 返回，不要随意漏题。
4. 答案只能包含 A/B/C/D；空题返回空字符串 ""。
5. 多选题按字母顺序输出，例如 "ABD"，不要输出 "DBA"。
6. 如果某题看不清，请根据涂卡痕迹输出最可能答案；完全没有涂卡才输出空字符串。
7. 最终必须是一个 JSON 对象。
"""


def build_json_repair_prompt(raw_content: str, page_num: int):
    """生成 JSON 修复提示词；输入模型原始输出，输出只修复格式的提示词。"""
    return f"""
下面是一段答题卡 OCR 的模型输出，但它不是合法 JSON。请只修复 JSON 格式，不要解释，不要使用 Markdown，不要新增无法从原文判断的信息。

要求：
1. 顶层必须是一个 JSON 对象。
2. page 使用 {page_num}。
3. answers 必须是数组。
4. 每个答案对象使用字段 "题号" 和 "答案"。
5. 答案只能包含 A/B/C/D，空题为 ""。

原始输出：
{raw_content}
"""


def validate_and_normalize_result(result: dict, page_num: int, min_answers: int = MIN_ACCEPTED_ANSWER_COUNT):
    """校验并整理识别结果；输入模型 JSON，输出批改流程可直接使用的数据。"""
    if not isinstance(result, dict):
        raise ValueError("模型返回的顶层结构不是 JSON 对象。")

    answers = result.get("answers")
    if not isinstance(answers, list):
        raise ValueError("模型返回结果缺少 answers 列表。")

    normalized_answers = []
    seen_questions = set()
    for item in answers:
        if not isinstance(item, dict):
            continue

        question_no = pick_value(item, QUESTION_KEYS)
        try:
            question_no = int(question_no)
        except (TypeError, ValueError):
            continue

        if question_no in seen_questions:
            continue

        seen_questions.add(question_no)
        normalized_answers.append(
            {
                QUESTION_KEY: question_no,
                ANSWER_KEY: normalize_answer(pick_value(item, ANSWER_KEYS)),
            }
        )

    normalized_answers.sort(key=lambda item: item[QUESTION_KEY])

    if len(normalized_answers) < min_answers:
        raise ValueError(f"有效答案数量过少：{len(normalized_answers)}，至少需要 {min_answers}。")

    return {
        "page": int(result.get("page") or page_num),
        "subject": str(result.get("subject") or "").strip(),
        "phone": str(result.get("phone") or "").strip(),
        "campus": str(result.get("campus") or "").strip(),
        "name": str(result.get("name") or "").strip(),
        "answers": normalized_answers,
    }


def request_chat_content(client, messages):
    """调用聊天接口；输入消息列表，输出模型文本内容。"""
    last_error = None

    # 外部接口偶发断连时，直接失败会中断整份答卷；这里做短重试，提高批量识别稳定性。
    for attempt in range(1, API_CALL_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model="mimo-v2.5",
                messages=messages,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                temperature=0,
            )
            return completion.choices[0].message.content
        except (APIConnectionError, APITimeoutError) as exc:
            last_error = exc
            if attempt < API_CALL_RETRIES:
                print(f"\n接口连接失败，正在重试 {attempt}/{API_CALL_RETRIES - 1} ...", flush=True)

    raise ValueError(f"接口连接失败，已重试 {API_CALL_RETRIES} 次：{last_error}")


def repair_and_parse_model_json(raw_content: str, page_num: int, client, min_answers: int):
    """修复模型返回的破损 JSON；输入原始文本，输出通过校验的识别结果。"""
    repaired_content = request_chat_content(
        client,
        [
            {"role": "system", "content": "You repair malformed OCR JSON. Return valid JSON only."},
            {"role": "user", "content": build_json_repair_prompt(raw_content, page_num)},
        ],
    )
    parsed = parse_model_json(repaired_content)
    return validate_and_normalize_result(parsed, page_num=page_num, min_answers=min_answers)


def recognize_one_page(page_num: int, image_base64: str, client=None, min_answers: int = MIN_ACCEPTED_ANSWER_COUNT):
    """识别单页答题卡；输入页码和图片 base64，输出学生作答 JSON。"""
    client = client or get_client()

    content = request_chat_content(
        client,
        [
            {"role": "system", "content": "You are a precise OCR assistant. Return valid JSON only."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                    {"type": "text", "text": build_prompt(page_num)},
                ],
            },
        ],
    )

    try:
        parsed = parse_model_json(content)
        return validate_and_normalize_result(parsed, page_num=page_num, min_answers=min_answers)
    except ValueError as first_error:
        try:
            result = repair_and_parse_model_json(content, page_num, client=client, min_answers=min_answers)
            result["json_repaired"] = True
            return result
        except ValueError as repair_error:
            error = f"{first_error}；JSON 修复也失败：{repair_error}"

        return {
            "page": page_num,
            "raw_output": content,
            "error": error,
        }


def recognize_page_with_retry(pdf_path: str, page_index: int, client):
    """识别单页并自动重试；输入 PDF、页索引和客户端，输出最终识别结果。"""
    last_error = None

    for profile in IMAGE_PROFILES:
        page_image = pdf_page_to_base64_image(
            pdf_path,
            page_index,
            dpi=profile["dpi"],
            contrast=profile["contrast"],
            sharpness=profile["sharpness"],
        )
        result = recognize_one_page(page_image["page"], page_image["base64"], client=client)

        if not result.get("error"):
            result["image_profile"] = profile["name"]
            return result

        last_error = result["error"]

    raise ValueError(f"第 {page_index + 1} 页识别失败：{last_error}")


def recognize_pdf_answers(pdf_path: str, show_progress: bool = True):
    """识别整份学生答题卡 PDF；输入 PDF 路径，输出每页学生答题数据列表。"""
    client = get_client()
    doc = fitz.open(pdf_path)

    try:
        page_count = len(doc)
    finally:
        doc.close()

    results = []
    if show_progress:
        print_progress(0, page_count)

    for page_index in range(page_count):
        try:
            results.append(recognize_page_with_retry(pdf_path, page_index, client))
        except Exception:
            if show_progress:
                print()
            raise

        if show_progress:
            print_progress(page_index + 1, page_count)

    return results


def save_results(data, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    results = recognize_pdf_answers(PDF_PATH)
    save_results(results, OUTPUT_JSON)
    print(f"识别完成，结果已保存到：{OUTPUT_JSON}")


if __name__ == "__main__":
    main()
