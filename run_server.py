from app import app, init_runtime_dirs


if __name__ == "__main__":
    # 本地开发入口：关闭 reloader，避免后台启动时父进程退出导致服务不可用。
    init_runtime_dirs()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

