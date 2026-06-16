# 试卷分发与批改系统

一个轻量级 Flask Web 系统，用于总校上传并下发试卷 PDF，分校上传学生答题卡，系统识别答案并生成批改报告，学生可按分校、姓名和手机号查询结果。

## 功能

- 总校：注册分校、上传试卷 PDF 和标准答案 PDF、选择分校下发。
- 分校：查看收到的试卷、预览/下载试卷、上传学生答题卡、发起批改。
- 学生：按分校、姓名、手机号查询试卷和批改结果。
- 识别：标准答案解析和学生答题卡识别结果统一保存到结果目录。
- 批改：根据选定的标准答案结果和学生答卷结果生成报告。

## 运行

```powershell
pip install -r requirements.txt
copy .env.example .env
python run_server.py
```

启动后访问：

```text
http://127.0.0.1:5000
```

## 项目结构

```text
app.py                    Flask 路由和业务流程
run_server.py             本地启动入口
standard_answers.py       标准答案 PDF 解析
recognize_answer_pdf.py   学生答题卡识别
mark_Test.py              批改并生成学生报告
requirements.txt          Python 依赖
templates/                页面模板
static/                   页面样式
data/                     运行时元数据，已忽略提交
storage/                  Web 上传文件和按考试归档的结果，已忽略提交
results/                  单独运行脚本时生成的识别/批改结果，已忽略提交
```

## 结果目录

Web 系统内，每场考试的结果会保存到：

```text
storage/exams/<exam_id>/results/standard/      标准答案解析结果
storage/exams/<exam_id>/results/students/      学生答卷识别结果
storage/exams/<exam_id>/results/reports/       批改报告
```

单独运行脚本时，默认保存到：

```text
results/standard/
results/students/
results/reports/
```

## 注意

- 学生答题卡识别会调用 MiMo 接口，需要在 `.env` 中配置 `MIMO_API_KEY`。
- `data/`、`storage/`、`results/` 都是运行时数据目录，不作为源码提交。
- 当前版本适合本地演示和小规模内部使用；正式上线前需要补充登录、权限和数据库。
