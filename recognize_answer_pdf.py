import base64
import json
import os
from pathlib import Path

import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

PDF_PATH = "题目/试卷/答卷.pdf"
OUTPUT_JSON = "students_answers.json"


def get_client():
    """创建 MiMo API 客户端；输入为空，输出 OpenAI 兼容客户端。"""
    return OpenAI(
        api_key=os.environ.get("MIMO_API_KEY"),
        base_url="https://api.xiaomimimo.com/v1",
    )


def pdf_page_to_base64_images(pdf_path: str, dpi: int = 200):
    """把 PDF 每一页转成 base64 图片；输入 PDF 路径和 DPI，输出页面图片列表。"""
    doc = fitz.open(pdf_path)
    images = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        image_bytes = pix.tobytes("png")

        images.append(
            {
                "page": page_index + 1,
                "base64": base64.b64encode(image_bytes).decode("utf-8"),
            }
        )

    doc.close()
    return images


def recognize_one_page(page_num: int, image_base64: str, client=None):
    """识别单页答题卡；输入页码和图片 base64，输出模型解析后的学生作答 JSON。"""
    client = client or get_client()

    prompt = """
你是一个答题卡识别助手。

请识别图片中的学生答题卡，并严格输出 JSON，不要输出任何解释文字。

需要提取以下字段：
{
  "page": 页码,
  "subject": "科目",
  "phone": "手机号",
  "campus": "校区",
  "name": "姓名",
  "answers": [
    {
      "题号": 1,
      "答案": "A"
    }
  ]
}

规则：
1. 科目一般在右上角，例如“科目：政治”。
2. 手机号、校区、姓名在表格上方。
3. 客观题通常有 33 题。
4. 答案只保留 A/B/C/D 字母。
5. 多选题答案按字母顺序输出，例如 "ABD"、"ABCD"。
6. 如果某题空白，答案输出 ""。
7. 如果识别不确定，仍尽量输出最可能结果。
8. 最终必须是合法 JSON。
"""

    completion = client.chat.completions.create(
        model="mimo-v2.5",
        messages=[
            {"role": "system", "content": "You are MiMo, an AI assistant developed by Xiaomi."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                    {"type": "text", "text": prompt + f"\n当前页码是：{page_num}"},
                ],
            },
        ],
        max_completion_tokens=2048,
        temperature=0,
    )

    content = completion.choices[0].message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "page": page_num,
            "raw_output": content,
            "error": "模型返回内容不是合法 JSON",
        }


def recognize_pdf_answers(pdf_path: str):
    """识别整份学生答题卡 PDF；输入 PDF 路径，输出每页学生答题数据列表。"""
    client = get_client()
    results = []

    for item in pdf_page_to_base64_images(pdf_path):
        results.append(recognize_one_page(item["page"], item["base64"], client=client))

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
