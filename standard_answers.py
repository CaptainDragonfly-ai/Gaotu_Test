import csv
import json
import re
from pathlib import Path

import fitz  # PyMuPDF


PDF_PATH = r"D:\desktop\高途面试\题目\试卷\考试题目\政治\【解析】26考研暑期营入营测试-政治.pdf"
OUTPUT_JSON = "results/standard/standard_answers.json"
OUTPUT_CSV = "results/standard/standard_answers.csv"


def extract_text_from_pdf(pdf_path: str) -> str:
    """从 PDF 中提取全部文本；输入 PDF 路径，输出合并后的纯文本。"""
    doc = fitz.open(pdf_path)
    all_text = []

    for page in doc:
        all_text.append(page.get_text("text"))

    doc.close()
    return "\n".join(all_text)


def clean_text(text: str) -> str:
    """清理页眉页脚和多余空行，让后续正则匹配更稳定。"""
    text = re.sub(r"第\s*\d+\s*页\s*/?\s*共\s*\d+\s*页", "", text)
    text = re.sub(r"参考答案及解析", "", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def parse_answer_analysis(text: str):
    """
    解析标准答案文本；输入答案解析文本，输出题号、答案、解析组成的列表。
    支持常见格式：1. 【答案】D 【解析】......
    """
    results = []
    pattern = re.compile(
        r"(\d+)\s*[\.、]\s*【答案】\s*([A-D]+)\s*【解析】\s*(.*?)(?=\n\s*\d+\s*[\.、]\s*【答案】|\Z)",
        re.S,
    )

    for question_no, answer, analysis in pattern.findall(text):
        results.append(
            {
                "题号": int(question_no),
                "答案": answer.strip(),
                "解析": re.sub(r"\s+", " ", analysis).strip(),
            }
        )

    return results


def parse_standard_pdf(pdf_path: str):
    """解析标准答案 PDF；输入 PDF 路径，输出标准答案列表，供 Web 上传流程调用。"""
    raw_text = extract_text_from_pdf(pdf_path)
    cleaned_text = clean_text(raw_text)
    return parse_answer_analysis(cleaned_text)


def save_to_json(data, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_to_csv(data, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["题号", "答案", "解析"])
        writer.writeheader()
        writer.writerows(data)


def main():
    data = parse_standard_pdf(PDF_PATH)
    save_to_json(data, OUTPUT_JSON)
    save_to_csv(data, OUTPUT_CSV)

    print(f"解析完成，共提取 {len(data)} 道题")
    print(f"JSON 已保存：{OUTPUT_JSON}")
    print(f"CSV 已保存：{OUTPUT_CSV}")


if __name__ == "__main__":
    main()
