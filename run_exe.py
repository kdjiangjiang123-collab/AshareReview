"""A股复盘助手 — EXE launcher (PyInstaller entry point).

Handles: first-run setup, lock file, port check, browser launch, Streamlit start.
"""
import os
import sys
import socket
import time
import subprocess
import webbrowser
import threading


def _app_dir() -> str:
    """Return the application root directory (works in dev and frozen modes)."""
    if getattr(sys, 'frozen', False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        # onedir: EXE is in the top folder, _internal/ is alongside it
        return d
    return os.path.dirname(os.path.abspath(__file__))


def _find_file(name: str, app_dir: str) -> str:
    """Locate a data file — check app root then _internal/ (PyInstaller onedir)."""
    for base in (app_dir, os.path.join(app_dir, "_internal")):
        path = os.path.join(base, name)
        if os.path.exists(path):
            return path
    return os.path.join(app_dir, name)


def _port_in_use(port: int = 8501) -> bool:
    """Return True if localhost:port is already listening."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def main():
    app_dir = _app_dir()
    os.chdir(app_dir)
    os.makedirs(os.path.join(app_dir, "data"), exist_ok=True)

    # ── Lock file: prevent double-launch ──
    lock_path = os.path.join(app_dir, ".lock")
    if os.path.exists(lock_path):
        age = time.time() - os.path.getmtime(lock_path)
        if age < 30:
            # Another instance is likely still alive — just open the browser
            webbrowser.open("http://localhost:8501")
            return
        # Stale lock — clean it up
        os.remove(lock_path)

    # ── First-run: create .env from template ──
    env_path = os.path.join(app_dir, ".env")
    if not os.path.exists(env_path):
        example = _find_file(".env.example", app_dir)
        content = ""
        if os.path.exists(example):
            with open(example, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = (
                "# A股复盘助手 — DeepSeek API 配置\n"
                "DEEPSEEK_API_KEY=sk-你的key\n"
                "DEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n"
                "DEEPSEEK_CHAT_MODEL=deepseek-chat\n"
                "DEEPSEEK_REASONER_MODEL=deepseek-reasoner\n"
            )
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("首次运行 — 请在弹出的 .env 文件中填入 DeepSeek API Key，保存后重新启动。")
        os.startfile(env_path)
        return

    # ── Validate API key ──
    with open(env_path, "r", encoding="utf-8") as f:
        env_text = f.read()
    if "sk-你的key" in env_text or "your-key" in env_text.lower():
        print("请先编辑 .env 文件填入 DeepSeek API Key，然后重新启动。")
        os.startfile(env_path)
        return
    if "DEEPSEEK_API_KEY=" not in env_text:
        print(".env 格式异常，请检查。")
        os.startfile(env_path)
        return

    # ── Already running? ──
    if _port_in_use(8501):
        print("检测到已有实例运行中，打开浏览器...")
        webbrowser.open("http://localhost:8501")
        return

    # ── Set up environment ──
    env = os.environ.copy()
    env.setdefault("NO_PROXY",
                   "eastmoney.com,*.eastmoney.com,gtimg.cn,*.gtimg.cn,"
                   "sina.com.cn,*.sina.com.cn,10jqka.com.cn,*.10jqka.com.cn")
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONWARNINGS"] = "ignore"

    # ── Start browser in background ──
    threading.Thread(target=lambda: (time.sleep(2), webbrowser.open("http://localhost:8501")),
                     daemon=True).start()

    # ── Launch Streamlit ──
    print("A股复盘助手 启动中... (首次启动需 10-20 秒)")
    with open(lock_path, "w") as lock_f:
        lock_f.write("")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.headless", "true",
             "--browser.gatherUsageStats", "false",
             "--server.fileWatcherType", "none",
             "--logger.level", "error"],
            cwd=app_dir, env=env,
        )
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)


if __name__ == "__main__":
    main()
