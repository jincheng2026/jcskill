"""测试用的小工具：假的家目录和工作文件夹、假的 TikHub 服务、跑命令。

所有测试都在系统临时文件夹里造假的家目录，不碰真实的文件；钥匙串一律换成测试专用的 service 名，
不读、不写、不删真实的 tikhub-api 条目；假 TikHub 只监听 127.0.0.1，不连外网。
FakeTikHub 的写法照 jincheng-workbench 仓库 skills/jincheng-workbench-research/tests/support.py（同一作者，MIT 许可）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
FIXTURES = os.path.join(HERE, "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

TEST_SERVICE = "jc-publish-closeout-test-not-real"
FAKE_KEY = "fake-tikhub-key-for-tests-0001"
DY_AWEME = "7400000000000000103"  # 和 fixtures 里 dy_detail.json 的作品一样
XHS_NOTE = "660000000000000000000001"  # 和 xhs_note_detail.json 的笔记一样
DY_HOME = "https://www.douyin.com/user/MS4wLjABAAAAfakeuser01"

OVERVIEW = """# 选题总览

## 选题总表

### 口播

**待做**

| 编号 | 选题 | 来源 | 状态 | 发布日期 | 效果 |
| --- | --- | --- | --- | --- | --- |
| T001 | 让 AI 帮你改简历 | 自己的想法 | 草稿 |  |  |
| T002 | 另一条 | 自己的想法 | 待写 |  |  |

**已做**

| 编号 | 选题 | 来源 | 状态 | 发布日期 | 效果 |
| --- | --- | --- | --- | --- | --- |

## 近三天内容安排

| 日期 | 安排 | 对应选题 |
| --- | --- | --- |
"""

CARD = """# T001 让 AI 帮你改简历

- **来源**：自己的想法
- **状态**：草稿
- **发布日期**：
- **效果**：

## 选题内容

- **写给谁**：要找工作的人
"""


class TempWork(object):
    """一个假的家目录，里面一个工作文件夹（有选题总览和一张选题卡）。"""

    def __init__(self):
        self.home = tempfile.mkdtemp(prefix="jc-closeout-test-")
        self.work = os.path.join(self.home, "Documents", "工作文件夹")
        os.makedirs(os.path.join(self.work, "内容草稿"))
        os.makedirs(os.path.join(self.work, "选题库", "口播", "待做"))
        with open(os.path.join(self.work, "选题库", "00_选题总览.md"), "w", encoding="utf-8") as f:
            f.write(OVERVIEW)
        with open(os.path.join(self.work, "选题库", "口播", "待做", "T001_让AI帮你改简历.md"), "w", encoding="utf-8") as f:
            f.write(CARD)

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("TIKHUB_") and not k.startswith("JC_")}
        env.update({"HOME": self.home, "JC_TIKHUB_KEYCHAIN_SERVICE": TEST_SERVICE, "PYTHONDONTWRITEBYTECODE": "1",
                    "JC_TIKHUB_PRICE_LOOKUP": "0", "TIKHUB_BASE_URL": "http://127.0.0.1:9"})
        env.update({k: v for k, v in extra.items() if v is not None})
        return env

    def path(self, *parts):
        return os.path.join(self.work, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return f.read()

    def write(self, name, text):
        path = os.path.join(self.home, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def archives(self):
        root = self.path("已发布")
        return sorted(os.path.join(root, n) for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)) and not n.startswith("."))

    def all_text(self):
        chunks = []
        for root, _dirs, files in os.walk(self.home):
            for name in files:
                with open(os.path.join(root, name), "rb") as f:
                    chunks.append(f.read().decode("utf-8", "replace"))
        return "\n".join(chunks)

    def cleanup(self):
        shutil.rmtree(self.home, ignore_errors=True)


def run_cli(args, env, cwd=None):
    """像 AI 那样在终端里跑命令，返回 (退出码, 输出)。"""
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "stats.py")] + list(args), env=env, cwd=cwd or env.get("HOME"),
                          capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout + done.stderr


def load_fixture(name, base=""):
    with open(os.path.join(FIXTURES, "tikhub", name), encoding="utf-8") as f:
        return json.loads(f.read().replace("{{BASE}}", base))


class FakeTikHub(object):
    """在 127.0.0.1 上起一个假的 TikHub。routes：{接口路径: 函数(参数) -> (状态码, 返回体, 等几秒)}。记下每次请求。"""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                parts = urlsplit(self.path)
                params = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
                outer.requests.append({"path": parts.path, "params": params, "auth": self.headers.get("Authorization")})
                if parts.path == "/api/v1/tikhub/user/get_user_info":
                    self._json(200, {"code": 200, "api_key_data": {"api_key_status": 1},
                                     "user_data": {"balance": 5, "free_credit": 0.05, "email_verified": True}})
                    return
                handler = outer.routes.get(parts.path)
                if handler is None:
                    self._json(404, {"detail": {"code": 404, "message": "Not Found"}})
                    return
                status, body, delay = handler(params)
                if delay:
                    time.sleep(delay)
                self._json(status, body)

            def _json(self, status, body):
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def paid(self):
        return [r for r in self.requests if "/tikhub/user/" not in r["path"]]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def ok(body):
    return lambda params: (200, body, 0)


def dy_detail(likes=None, play=None):
    """dy_detail.json，可以改点赞数和播放数（模拟 12 小时、7 天两次抓到的数不一样）。"""
    body = load_fixture("dy_detail.json")
    stats = body["data"]["aweme_detail"]["statistics"]
    if likes is not None:
        stats["digg_count"] = likes
    if play is not None:
        stats["play_count"] = play
    return body
