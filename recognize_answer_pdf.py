import os
import json
import base64
import fitz  # pip install pymupdf
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("MIMO_API_KEY"),
    base_url="https://api.xiaomimimo.com/v1"
)

PDF_PATH = f"题目/试卷/答卷.pdf"
OUTPUT_JSON = "students_answers.json"


def pdf_page_to_base64_images(pdf_path: str, dpi: int = 200):
    """
    将 PDF 每一页转成 base64 图片
    """
    doc = fitz.open(pdf_path)
    images = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        image_bytes = pix.tobytes("png")
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        images.append({
            "page": page_index + 1,
            "base64": image_base64
        })

    return images


def recognize_one_page(page_num: int, image_base64: str):
    """
    调用 MiMo 视觉模型识别单页答题卡
    """

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
3. 客观题共有 33 题。
4. 答案只保留 A/B/C/D 字母。
5. 多选题答案按字母顺序输出，例如 "ABD"、"ABCD"。
6. 如果某题空白，答案输出 ""。
7. 如果识别不确定，仍尽量输出最可能结果。
8. 最终必须是合法 JSON。
"""

    completion = client.chat.completions.create(
        model="mimo-v2.5",
        messages=[
            {
                "role": "system",
                "content": "You are MiMo, an AI assistant developed by Xiaomi."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt + f"\n当前页码是：{page_num}"
                    }
                ]
            }
        ],
        max_completion_tokens=2048,
        temperature=0
    )

    content = completion.choices[0].message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "page": page_num,
            "raw_output": content,
            "error": "模型返回内容不是合法 JSON"
        }


def main():
    page_images = pdf_page_to_base64_images(PDF_PATH)

    results = []

    for item in page_images:
        page_num = item["page"]
        print(f"正在识别第 {page_num} 页...")

        result = recognize_one_page(
            page_num=page_num,
            image_base64=item["base64"]
        )

        results.append(result)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"识别完成，结果已保存到：{OUTPUT_JSON}")


if __name__ == "__main__":
    main()