#!/usr/bin/env python3
"""JC 内容创作系列的体检：装了哪些 Skill、工作文件夹在哪、本机工具和两样 key 齐不齐、有没有到点没抓的数据。

  python3 doctor.py           # 给 AI 读的简短清单
  python3 doctor.py --json

只读不写：不建文件夹、不读出任何 key 的内容（钥匙串只查条目在不在）。只用 Python 自带的模块。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
sys.path.insert(0, str(HERE))
import init_workfolder as wf  # noqa: E402

SERIES = [
    ("调研对标", "jc-media-research"),
    ("调研对标", "jc-benchmark-intake"),
    ("拆解对标", "jc-video-analysis"),
    ("生成内容", "jc-jiaocheng-video"),
    ("生成内容", "jc-zhuanxie"),
    ("生成内容", "jc-gongzuotai-write"),
    ("生成内容", "jc-jianjie"),
    ("生成内容", "jc-koubo-shuping"),
    ("发布", "jc-publish-closeout"),
    ("复盘", "jc-media-review"),
    ("迭代", "jc-skill-writer"),
]
KEYS = {
    "火山引擎豆包语音（转文字）": ("VOLC_SPEECH_API_KEY", os.environ.get("JC_VOLC_KEYCHAIN_SERVICE") or "volc-speech-api", "volc"),
    "TikHub（抓数据和评论）": ("TIKHUB_API_KEY", os.environ.get("JC_TIKHUB_KEYCHAIN_SERVICE") or "tikhub-api", "tikhub"),
}


def key_status(env_name, service, account):
    """只说在不在、在哪，不取出 key。"""
    if (os.environ.get(env_name) or "").strip():
        return "环境变量 " + env_name
    security = "/usr/bin/security"
    if not os.path.exists(security):
        return None
    try:
        done = subprocess.run([security, "find-generic-password", "-s", service, "-a", account],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return "钥匙串" if done.returncode == 0 else None


def find_workbench():
    for cand in (Path.home() / "jincheng-workbench",):
        if (cand / "creation-page" / "where.py").is_file():
            return str(cand)
    return None


def due_points(workfolder):
    stats = SKILL_DIR.parent / "jc-publish-closeout" / "scripts" / "stats.py"
    if not workfolder or not stats.is_file():
        return None
    try:
        done = subprocess.run([sys.executable, str(stats), "due", "--workfolder", str(workfolder)],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (done.stdout or "").strip()
    if not text or text.startswith("还没有") or "没有到点" in text:
        return None
    return text


def main():
    ap = argparse.ArgumentParser(description="JC 内容创作系列体检（只读）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    skills_root = SKILL_DIR.parent
    installed = {name: (skills_root / name / "SKILL.md").is_file() for _, name in SERIES}
    folder, how = wf.find(Path.cwd())
    tools = {t: bool(shutil.which(t)) for t in ("python3", "ffmpeg", "ffprobe", "node", "git")}
    keys = {label: key_status(*spec) for label, spec in KEYS.items()}
    workbench = find_workbench()
    due = due_points(folder)
    out = {
        "skills_dir": str(skills_root),
        "installed": installed,
        "workfolder": str(folder) if folder else None,
        "workfolder_how": how,
        "tools": tools,
        "keys": keys,
        "workbench": workbench,
        "due": due,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    missing = [n for n, ok in installed.items() if not ok]
    print("Skill：" + ("本系列 12 个都装好了（总入口 jc 加 11 个）" if not missing else "缺 " + "、".join(missing)) + f"（装在 {skills_root}）")
    print("工作文件夹：" + (f"{folder}（{how}）" if folder else f"还没有，第一次用时建在 {wf.DEFAULT}"))
    lack = [t for t, ok in tools.items() if not ok]
    print("本机工具：" + ("python3、ffmpeg、ffprobe、node、git 都有" if not lack else "缺 " + "、".join(lack)))
    for label, where in keys.items():
        print(f"{label} 的 key：" + (f"已配好（{where}）" if where else "还没配，用到时再配"))
    print("创作工作台：" + (f"装在 {workbench}" if workbench else "没在默认位置找到（做创作页时再装）"))
    if due:
        print("到点的数据：\n" + due)
    return 0


if __name__ == "__main__":
    sys.exit(main())
