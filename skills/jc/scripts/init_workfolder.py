#!/usr/bin/env python3
"""找到或建好「工作文件夹」：JC 内容创作系列和创作工作台（jincheng-workbench）共用的那个文件夹。

  python3 init_workfolder.py              # 找到就打印位置；找不到就在默认位置建好
  python3 init_workfolder.py --find       # 只找，不建（找不到时退出码 1）
  python3 init_workfolder.py --at <路径>  # 在指定位置建（只补缺的）
  python3 init_workfolder.py --json       # 输出 JSON

找的顺序：当前文件夹或它往上几层里有「内容草稿/」或「选题库/00_选题总览.md」的；
创作工作台设置文件里的 workFolder；~/Documents/jincheng-workbench/。
建的时候只补缺的文件和文件夹，从不覆盖已有文件。只用 Python 自带的模块。
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "workfolder"
DEFAULT = Path.home() / "Documents" / "jincheng-workbench"
WORKBENCH_CONFIG = Path.home() / "Library" / "Application Support" / "jincheng-workbench" / "config.json"
TYPES = ("教程", "科普", "口播")
FOLDERS = [
    "内容草稿",
    "写稿方法",
    "市场调研/对标账号",
    "市场调研/调研报告",
    "市场调研/评论导入",
    "市场调研/对标素材/未参考",
    "市场调研/对标素材/已参考",
    "已发布",
    "回收站",
] + [f"选题库/{t}/{g}" for t in TYPES for g in ("待做", "已做")]


def looks_like_workfolder(folder: Path) -> bool:
    return (folder / "内容草稿").is_dir() or (folder / "选题库" / "00_选题总览.md").is_file()


def from_workbench_config():
    config = Path(os.environ.get("JC_WORKBENCH_CONFIG") or WORKBENCH_CONFIG)
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = str(data.get("workFolder") or "").strip()
    if not value:
        return None
    if value == "~" or value.startswith("~/"):
        value = str(Path.home()) + value[1:]
    return Path(value)


def find(start: Path):
    """返回 (位置, 怎么找到的)；找不到返回 (None, None)。"""
    here = start.resolve()
    for folder in [here, *here.parents][:6]:
        if folder == Path.home() or folder == Path("/"):
            break
        if looks_like_workfolder(folder):
            return folder, "当前打开的文件夹"
    wb = from_workbench_config()
    if wb and wb.is_dir():
        return wb, "创作工作台的设置"
    if DEFAULT.is_dir():
        return DEFAULT, "默认位置"
    return None, None


def ensure(root: Path):
    """只补缺的：返回这次新建的文件夹和文件（相对路径）。"""
    created = []
    if not root.exists():
        root.mkdir(parents=True)
        created.append(".")
    for rel in FOLDERS:
        d = root / rel
        if not d.exists():
            d.mkdir(parents=True)
            created.append(rel + "/")
    for src in sorted(TEMPLATE.rglob("*")):
        if not src.is_file() or src.name.startswith("."):
            continue
        rel = src.relative_to(TEMPLATE)
        dst = root / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        created.append(str(rel))
    return created


def main():
    ap = argparse.ArgumentParser(description="找到或建好工作文件夹（只补缺的，不覆盖）")
    ap.add_argument("--find", action="store_true", help="只找，不建")
    ap.add_argument("--at", help="在这个位置建（只补缺的）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.at:
        root, how = Path(os.path.expanduser(args.at)).resolve(), "指定位置"
    else:
        root, how = find(Path.cwd())
    if root is None and args.find:
        out = {"found": False, "default": str(DEFAULT)}
        print(json.dumps(out, ensure_ascii=False) if args.json else f"还没有工作文件夹（默认会建在 {DEFAULT}）")
        return 1
    if root is None:
        root, how = DEFAULT, "新建在默认位置"
    created = [] if args.find else ensure(root)
    out = {"found": True, "workfolder": str(root), "how": how, "created": created}
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(f"工作文件夹：{root}（{how}）")
        if created:
            print(f"这次补建了 {len(created)} 项：" + "、".join(created[:12]) + ("……" if len(created) > 12 else ""))
        elif not args.find:
            print("该有的都有，没有新建任何东西。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
