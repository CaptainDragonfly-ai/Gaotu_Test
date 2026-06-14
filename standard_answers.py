import re
import json
import csv
import fitz  # PyMuPDF


PDF_PATH = "题目/试卷/考试题目/政治/【解析】26考研暑期营入营测试-政治.pdf"
OUTPUT_JSON = "standard_answers.json"
OUTPUT_CSV = "standard_answers.csv"


def extract_text_from_pdf(pdf_path: str) -> str:
    """从 PDF 中提取全部文本"""
    doc = fitz.open(pdf_path)
    all_text = []

    for page in doc:
        text = page.get_text("text")
        all_text.append(text)

    doc.close()
    return "\n".join(all_text)


def clean_text(text: str) -> str:
    """清洗页眉页脚等干扰信息"""
    text = re.sub(r"第\d+页/共\d+页", "", text)
    text = re.sub(r"26 考研暑期营入营测-政治", "", text)
    text = re.sub(r"参考答案及解析", "", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def parse_answer_analysis(text: str):
    """
    解析格式：
    1. 【答案】D
    【解析】xxxx
    """
    results = []

    pattern = re.compile(
        r"(\d+)\.\s*【答案】\s*([A-D]+)\s*"
        r"【解析】(.*?)(?=\n\d+\.\s*【答案】|\Z)",
        re.S
    )

    matches = pattern.findall(text)

    for question_no, answer, analysis in matches:
        analysis = analysis.strip()
        analysis = re.sub(r"\s+", " ", analysis)

        results.append({
            "题号": int(question_no),
            "答案": answer.strip(),
            "解析": analysis
        })

    return results


def save_to_json(data, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_to_csv(data, output_path: str):
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["题号", "答案", "解析"])
        writer.writeheader()
        writer.writerows(data)


def main():
    raw_text = extract_text_from_pdf(PDF_PATH)
    cleaned_text = clean_text(raw_text)

    data = parse_answer_analysis(cleaned_text)

    save_to_json(data, OUTPUT_JSON)
    save_to_csv(data, OUTPUT_CSV)

    print(f"解析完成，共提取 {len(data)} 道题")
    print(f"JSON 已保存：{OUTPUT_JSON}")
    print(f"CSV 已保存：{OUTPUT_CSV}")

    for item in data[:3]:
        print(item)


if __name__ == "__main__":
    main()