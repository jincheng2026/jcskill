"""找工作文件夹、找档案。

工作文件夹和创作工作台（jincheng-workbench）是同一个，按这个顺序找，找到就停：
1. 当前文件夹或者它往上几层，里面有 内容草稿/ 或 选题库/00_选题总览.md；
2. 创作工作台的设置 ~/Library/Application Support/jincheng-workbench/config.json 里的 workFolder；
3. ~/Documents/jincheng-workbench/ 存在。
都没有返回 None，由调用的人决定怎么办。
"""
import json
import os

from . import UserError

PUBLISHED = "已发布"
OVERVIEW_NAME = "00_已发布总览.md"
ACCOUNTS_NAME = "我的账号.md"
HIDDEN = ".tikhub"  # TikHub 用量记录和解析不出来时存的原始返回，以点开头，工作台不显示
TOPICS_OVERVIEW = os.path.join("选题库", "00_选题总览.md")


def _home(env):
    return env.get("HOME") or os.path.expanduser("~")


def _expand(value, home):
    value = str(value).strip()
    if value == "~":
        return home
    return os.path.join(home, value[2:]) if value.startswith("~/") else value


def _looks_like_workfolder(folder):
    return os.path.isdir(os.path.join(folder, "内容草稿")) or os.path.isfile(os.path.join(folder, TOPICS_OVERVIEW))


def find_workfolder(env=None, cwd=None):
    env = os.environ if env is None else env
    home = _home(env)
    folder = os.path.abspath(cwd or os.getcwd())
    for _ in range(6):
        if _looks_like_workfolder(folder):
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    config = os.path.join(home, "Library", "Application Support", "jincheng-workbench", "config.json")
    if os.path.isfile(config):
        try:
            with open(config, encoding="utf-8-sig") as f:
                raw = json.load(f)
            work = raw.get("workFolder") if isinstance(raw, dict) else None
            if isinstance(work, str) and work.strip():
                path = os.path.abspath(_expand(work, home))
                if os.path.isdir(path):
                    return path
        except (OSError, ValueError):
            pass
    default = os.path.join(home, "Documents", "jincheng-workbench")
    return default if os.path.isdir(default) else None


def workfolder_or_die(given, env=None):
    if given:
        path = os.path.abspath(_expand(given, _home(env or os.environ)))
        if not os.path.isdir(path):
            raise UserError("工作文件夹不存在：%s。先确认路径对不对。" % path)
        return path
    found = find_workfolder(env)
    if not found:
        raise UserError("找不到工作文件夹。用 --workfolder 告诉我在哪；还没有的话，先用总入口 jc 的建文件夹脚本建一个。")
    return found


def published_dir(workfolder):
    return os.path.join(workfolder, PUBLISHED)


def hidden_dir(workfolder):
    return os.path.join(published_dir(workfolder), HIDDEN)


def archive_dir(text, workfolder=None):
    """档案文件夹：可以写完整路径，也可以只写「已发布」里的文件夹名（这时要知道工作文件夹）。"""
    text = str(text or "").strip()
    if not text:
        raise UserError("要告诉我是哪个档案（「已发布」里的文件夹名，或者完整路径）。")
    candidate = os.path.abspath(os.path.expanduser(text))
    if os.path.isfile(os.path.join(candidate, "内容.md")):
        return candidate
    if workfolder:
        inside = os.path.join(published_dir(workfolder), text)
        if os.path.isfile(os.path.join(inside, "内容.md")):
            return inside
    raise UserError("找不到档案「%s」：那里没有 内容.md。档案在工作文件夹的「已发布」里，一条视频一个文件夹。" % text)


def workfolder_of_archive(archive):
    """档案放在 <工作文件夹>/已发布/<档案>/，往上两层就是工作文件夹。"""
    parent = os.path.dirname(os.path.abspath(archive))
    if os.path.basename(parent) == PUBLISHED:
        return os.path.dirname(parent)
    return None


def list_archives(workfolder):
    root = published_dir(workfolder)
    try:
        names = sorted(n for n in os.listdir(root) if not n.startswith((".", "_")))
    except OSError:
        return []
    return [os.path.join(root, n) for n in names if os.path.isfile(os.path.join(root, n, "内容.md"))]
