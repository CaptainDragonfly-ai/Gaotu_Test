# 试卷分发系统

一个轻量的 Flask Web 系统，用于总校下发试卷 PDF、分校上传答题卡和答案并批改、学生查询试卷和成绩。

## 功能

- 总校：注册分校、上传试卷 PDF、选择指定分校下发、在线预览和下载试卷。
- 分校：查看收到的试卷、预览下载、上传总部答案 PDF、上传学生答题卡 PDF、生成批改报告。
- 学生：通过分校、姓名、手机号查询试卷下载入口和批改结果。

## 运行

```bash
pip install -r requirements.txt
copy .env.example .env
python run_server.py
```

启动后访问：

```text
http://127.0.0.1:5000
```

## 目录

```text
app.py                  Web 路由和业务流程
run_server.py           本地启动入口
standard_answers.py     解析总部答案 PDF
recognize_answer_pdf.py 识别学生答题卡 PDF
mark_Test.py            批改并生成学生报告
templates/              页面模板
static/                 后台样式
data/                   本地 JSON 元数据，运行时生成
storage/                上传文件和批改报告，运行时生成
```

## 数据说明

系统使用本地 JSON 和文件目录管理数据，适合本地演示和小规模内部使用。`data/app_data.json` 保存分校、试卷和下发记录；`storage/` 保存上传的 PDF、解析结果和学生报告。这两个运行时目录已加入 `.gitignore`。

## 注意

- 学生答题卡识别会调用 MiMo 接口，需要在 `.env` 中配置 `MIMO_API_KEY`。
- 当前版本是内部原型，没有登录鉴权；上线前应增加账号、权限和数据库。
