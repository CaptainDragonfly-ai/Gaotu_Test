# Gaotu 项目协作指南

## 全局写作与代码风格

- 给用户写代码时，重要逻辑要添加中文注释。
- 注释要说明代码做什么，以及为什么这样写。
- 不要机械地给每一行加注释，明显语句可以不注释。
- 新增函数时，添加简短注释，说明用途、输入和输出。
- 修改代码后，要总结改了哪些内容、涉及哪些文件。
- 教学、解释、排查问题时，尽量使用适合初学者理解的表达。

## 项目定位

- 当前项目位于 `D:\CodeX\Gaotu`。
- 这是一个轻量级 Flask Web 系统，用于试卷分发、答题卡识别、自动批改和学生成绩查询。
- 当前实现更适合本地演示和小规模内部使用，不是完整生产系统。
- 项目没有数据库服务，运行数据存放在本地 JSON 文件和本地文件夹中。

## 技术栈

- 后端：Flask。
- PDF 处理：PyMuPDF。
- 学生答题卡识别：通过 OpenAI SDK 兼容客户端调用 MiMo 接口。
- 图片增强：Pillow。
- 环境变量：`python-dotenv` 读取 `.env`。
- 前端：Jinja2 模板 + 原生 CSS + 少量原生 JavaScript。

## 运行方式

```powershell
pip install -r requirements.txt
copy .env.example .env
python run_server.py
```

- 本地访问地址：`http://127.0.0.1:5000`
- `run_server.py` 是推荐的本地启动入口。
- `run_server.py` 会关闭 Flask reloader，避免托管环境或后台启动时父进程退出导致服务不可用。
- 学生答题卡识别需要在 `.env` 中配置 `MIMO_API_KEY`。

## 关键文件

- `app.py`：Flask 应用入口，包含总校、分校、学生查询、文件预览和下载等主要路由。
- `run_server.py`：本地启动入口。
- `standard_answers.py`：解析标准答案 PDF，输出标准答案 JSON/CSV。
- `recognize_answer_pdf.py`：识别学生答题卡 PDF，调用 MiMo 接口并清洗模型返回。
- `mark_Test.py`：根据标准答案和学生答案进行批改，并生成学生报告 JSON。
- `templates/base.html`：页面基础布局，包含左侧导航和消息提示。
- `templates/headquarters.html`：总校上传试卷、上传标准答案、选择分校并下发。
- `templates/branch.html`：分校选择和已收到试卷列表。
- `templates/branch_exam.html`：分校处理单场考试，预览试卷/答案、上传答题卡、选择答案集并批改。
- `templates/student.html`：学生按分校、姓名、手机号查询成绩。
- `templates/student_report.html`：学生成绩详情和错题明细。
- `static/styles.css`：后台管理风格的页面样式。

## 运行时目录和提交注意事项

- `data/app_data.json`：本地 JSON 元数据，保存分校、考试、下发记录。
- `storage/`：Web 上传文件和按考试归档的识别、批改结果。
- `results/`：脚本单独运行时生成的识别或批改结果。
- `.env`：本地密钥配置。
- 以上运行时数据和密钥不应提交到 Git。
- `.gitignore` 已忽略 `.env`、`data/app_data.json`、`storage/`、`results/`、缓存目录等本地文件。

## 数据结构要点

`data/app_data.json` 顶层结构：

```json
{
  "campuses": [],
  "exams": [],
  "deliveries": {}
}
```

- `campuses` 保存分校信息，主要字段是 `id`、`name`、`code`。
- `exams` 保存总校创建的考试，主要字段是 `id`、`title`、`subject`、`paper_path`、`standard_pdf_path`、`standard_json_path`、`recipients`、`created_at`。
- `deliveries` 使用 `exam_id:campus_id` 作为键，保存某场考试下发到某个分校后的处理状态。
- `deliveries` 中的关键字段包括 `student_pdf_path`、`standard_pdf_path`、`student_json_path`、`standard_json_path`、`standard_answer_sets`、`student_answer_sets`、`report_dir`、`report_count`、`status`、`updated_at`。

## 核心业务流程

1. 总校在 `/headquarters` 注册分校。
2. 总校上传试卷 PDF 和标准答案 PDF，选择接收分校后成套下发。
3. 系统解析标准答案 PDF，生成标准答案 JSON，并写入考试记录和每个分校的下发记录。
4. 分校在 `/branch` 选择当前分校，进入具体考试处理页。
5. 分校在 `/branch/<campus_id>/exam/<exam_id>` 预览试卷和答案，上传学生答题卡 PDF。
6. 系统调用 MiMo 识别学生答题卡，生成学生答案 JSON，并加入 `student_answer_sets`。
7. 分校明确选择标准答案集和学生答案集后开始批改。
8. 系统生成学生报告 JSON，学生可在 `/student` 用分校、姓名、手机号查询成绩和错题明细。

## 重要实现细节

- 总校下发时，试卷 PDF 和标准答案 PDF 是一套，不能把标准答案设计成分校后续可选上传。
- 批改时必须显式选择 `standard_set_id` 和 `student_set_id`，不要恢复成“默认使用最新文件”的隐式逻辑。
- `ensure_delivery_sets()` 用于兼容旧数据，把旧的单个答案路径补齐成可选择的答案集。
- 分校考试页的 PDF 预览使用同一个 `iframe#pdfPreview`，通过 `currentDownload` 保持下载按钮与当前预览文件一致。
- 总校分校选择器支持按分校名称/编码搜索，并且“全选”只选择当前过滤结果。
- 文件预览和下载必须通过 `storage_file_exists()` 校验，确保只能访问 `storage/` 下的文件。

## 识别与批改注意事项

- `recognize_answer_pdf.py` 是学生答题卡识别入口，`app.py` 只负责调用并展示错误。
- 模型返回可能是纯 JSON、Markdown fenced JSON，或带有额外说明文字的 JSON。`parse_model_json()` 已做容错解析。
- 如果模型返回无法解析，`recognize_one_page()` 会尝试再调用模型修复 JSON。
- 如果整页识别失败，`recognize_pdf_answers()` 应该抛出错误，不要把坏结果保存到 `student_answer_sets`。
- 自动化测试或回归验证不要把真实业务试卷发到外部 API；优先使用 mock、合成样例或本地逻辑测试。
- `mark_Test.py` 会把多选答案标准化，例如 `DBA` 和 `ABD` 会被视为同一个答案。

## 路由速查

- `GET /`：重定向到总校页面。
- `GET, POST /headquarters`：总校下发试卷套件。
- `POST /campuses`：新增分校。
- `POST /campuses/<campus_id>/delete`：删除分校及其下发关系。
- `GET /branch`：分校试卷列表。
- `GET, POST /branch/<campus_id>/exam/<exam_id>`：分校处理单场考试。
- `GET, POST /student`：学生查询。
- `GET /student/report?path=...`：学生报告详情。
- `GET /files/preview?path=...`：PDF 预览。
- `GET /files/download?path=...`：文件下载。

## 验证建议

- 修改 Python 代码后，优先运行：

```powershell
python -m compileall app.py run_server.py standard_answers.py recognize_answer_pdf.py mark_Test.py
```

- 修改 Flask 路由或模板后，可用 Flask test client 检查 `/headquarters`、`/branch`、`/student` 是否返回 `200`。
- 当前项目没有稳定提交的测试目录时，不要声称已经跑过完整测试。
- 如果未来补充测试，学生答题卡识别部分应 mock 外部 API，避免调用真实 MiMo 接口。

## UI 维护方向

- 界面风格保持干净、克制的企业后台风格。
- 避免在列表页增加重复入口；详细预览和处理动作应集中在分校考试处理页。
- 页面要优先保证流程清晰：总校下发、分校处理、学生查询三条主线不要混在一起。
- 移动端已有基础响应式样式，新增布局时要检查窄屏下表单和表格不会互相挤压。

## 已知环境注意事项

- Windows/PowerShell 环境下，终端可能出现中文编码乱码；编辑文件时仍应使用 UTF-8。
- 运行服务时优先用短生命周期验证或 Flask test client，后台进程在托管环境中可能不稳定。
- 发布到 GitHub 时，如果遇到 Git ownership 或代理问题，可用按命令配置的方式处理，不要随意改全局配置。
