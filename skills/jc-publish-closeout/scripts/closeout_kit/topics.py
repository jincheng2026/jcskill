"""发布以后改选题：选题总览里这一行的「状态」改成「已发布」（「发布日期」空着才填），选题卡挪到同一类的「已做/」。

选题总览的格式和创作工作台（jincheng-workbench 的 lib/templates.mjs、lib/works.mjs）一样：
「## 选题总表」下面每个内容类型一节（### 类型），里面「**待做**」「**已做**」两张表，
表头是「编号 | 选题 | 来源 | 状态 | 发布日期 | 效果」。工作台看到状态是「已发布」就把它算作做完了。
这里只改那一行的两格，不挪行、不动表头和别的行；认不出格式就停下说明，不硬改。
"""
import os
import re
import shutil

from . import UserError
from .archive import _cells
from .text import write_text

STATUS = "已发布"


def _row_id(cells, head):
    if "编号" not in head:
        return None
    m = re.search(r"T\d{3,4}(?!\d)", cells[head.index("编号")] if head.index("编号") < len(cells) else "")
    return m.group(0) if m else None


def mark_overview(path, content_id, date):
    """返回一句说明。找不到文件或这一行，抛 UserError（不新建行）。"""
    if not os.path.isfile(path):
        raise UserError("没有选题总览（%s），选题状态没改。" % path)
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().split("\n")
    section, head, hit = "", None, None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("## "):
            section, head = line[3:].strip(), None
            continue
        if not line.startswith("|"):
            head = None
            continue
        cells = _cells(line)
        if cells and all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
            continue
        if head is None:
            head = cells
            continue
        if section.startswith("选题总表") and _row_id(cells, head) == content_id:
            hit = (i, head, cells)
            break
    if not hit:
        raise UserError("选题总览里没找到 %s 这一行，选题状态没改。请用户确认编号对不对。" % content_id)
    i, head, cells = hit
    if "状态" not in head:
        raise UserError("选题总览的表头里没有「状态」这一列，没改。照创作工作台的格式（编号 | 选题 | 来源 | 状态 | 发布日期 | 效果）改好再来。")
    while len(cells) < len(head):
        cells.append("")
    changed = []
    if cells[head.index("状态")] != STATUS:
        cells[head.index("状态")] = STATUS
        changed.append("状态改成「已发布」")
    if "发布日期" in head and not cells[head.index("发布日期")].strip() and date:
        cells[head.index("发布日期")] = date
        changed.append("发布日期填 %s" % date)
    if not changed:
        return "选题总览里 %s 已经是「已发布」，没改。" % content_id
    lines[i] = "| " + " | ".join(cells) + " |"
    write_text(path, "\n".join(lines))
    return "选题总览里 %s：%s。" % (content_id, "，".join(changed))


def _cards(topics_dir, content_id):
    found = []
    if not os.path.isdir(topics_dir):
        return found
    for root, dirs, files in os.walk(topics_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        depth = os.path.relpath(root, topics_dir).count(os.sep)
        if depth > 2:
            continue
        for name in files:
            if name.endswith(".md") and re.match(r"^%s(?:[_ ]|\.md$)" % re.escape(content_id), name):
                found.append(os.path.join(root, name))
    return sorted(found)


def _update_card(path, date):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    new = re.sub(r"^(-\s*\*\*状态\*\*[:：]).*$", r"\1" + STATUS, text, count=1, flags=re.M)
    if date:
        new = re.sub(r"^(-\s*\*\*发布日期\*\*[:：])[ \t]*$", r"\g<1>" + date, new, count=1, flags=re.M)
    if new != text:
        write_text(path, new)


def move_card(topics_dir, content_id, date):
    """选题卡挪到 <类型>/已做/，顺手把卡上的「状态」「发布日期」改成一致。返回一句说明。"""
    cards = _cards(topics_dir, content_id)
    if not cards:
        return "没找到 %s 的选题卡，没挪。" % content_id
    if len(cards) > 1:
        return "%s 有 %d 张选题卡（%s），没挪，请用户说用哪张。" % (content_id, len(cards), "、".join(os.path.relpath(c, topics_dir) for c in cards))
    card = cards[0]
    _update_card(card, date)
    folder = os.path.dirname(card)
    if os.path.basename(folder) == "已做":
        return "选题卡已经在「已做」里了。"
    type_dir = os.path.dirname(folder) if os.path.basename(folder) == "待做" else folder
    target_dir = os.path.join(type_dir, "已做")
    target = os.path.join(target_dir, os.path.basename(card))
    if os.path.exists(target):
        return "「已做」里已经有同名的选题卡，没挪：%s" % os.path.relpath(target, topics_dir)
    os.makedirs(target_dir, exist_ok=True)
    shutil.move(card, target)
    return "选题卡挪到了 %s。" % os.path.relpath(target, os.path.dirname(topics_dir))


def mark_published(workfolder, content_id, date, overview=None):
    topics_dir = os.path.join(workfolder, "选题库")
    path = overview or os.path.join(topics_dir, "00_选题总览.md")
    notes = []
    try:
        notes.append(mark_overview(path, content_id, date))
    except UserError as e:
        notes.append(str(e))
    notes.append(move_card(topics_dir, content_id, date))
    return notes
