#!/usr/bin/env python3
"""Deterministic research calculations and validation. Semantics and prose are supplied by the Agent."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import html
import json
import math
from pathlib import Path
import re
import statistics

class DecisionError(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

def date(value):
    if not value: return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

def group_key(row):
    keys = ("platform", "author_id", "content_type", "collection_batch_id")
    return tuple(row.get(k) for k in keys) if all(row.get(k) for k in keys) else None

def upgrade_content(payload):
    result = deepcopy(payload)
    if str(result.get("schema_version", 1)) not in {"1", "1.0", "2"}:
        raise DecisionError("不支持的数据版本")
    result["schema_version"] = 2
    for r in result.get("records", []):
        r["schema_version"] = 2
        for key in ("author_id", "content_type", "collection_batch_id", "follower_snapshot_at",
                    "view_count_reliable", "topic_id"):
            r.setdefault(key, None)
    return result

def calculate_baselines(payload, as_of=None, min_samples=10, max_samples=30, min_age_days=7, max_age_days=90):
    result = upgrade_content(payload)
    reference = date(as_of or result.get("as_of"))
    if reference is None:
        raise DecisionError("基线计算需要明确的 as_of")
    if min_samples < 1 or max_samples < min_samples or min_age_days < 0 or max_age_days < min_age_days:
        raise DecisionError("基线样本参数无效")
    result["baseline_policy"] = {"as_of": reference.isoformat(), "min_samples": min_samples,
        "max_samples": max_samples, "min_age_days": min_age_days, "max_age_days": max_age_days,
        "group_fields": ["platform", "author_id", "content_type", "collection_batch_id"],
        "exclude_target": True, "estimator": "median"}
    # Preserve distinct collection batches. A later snapshot within one batch replaces its duplicate.
    seen, missing = {}, []
    for r in result.get("records", []):
        if not r.get("content_id"):
            missing.append(r)
            continue
        key = (r.get("platform"), r["content_id"], r.get("collection_batch_id"))
        prior = seen.get(key)
        if prior is None or str(r.get("collected_at") or "") >= str(prior.get("collected_at") or ""):
            seen[key] = r
    result["records"] = list(seen.values()) + missing
    groups = defaultdict(list)
    for r in result["records"]:
        if group_key(r): groups[group_key(r)].append(r)
    for members in groups.values():
        # One metric for the whole group, including targets. Zero views alone is not proof of reliability.
        metric = "view_count" if all(number(r.get("view_count")) and r.get("view_count_reliable") is True
                                     for r in members) else "like_count"
        mature = []
        for r in members:
            published = date(r.get("published_at"))
            age = (reference - published).total_seconds() / 86400 if published else None
            r["baseline_target_mature"] = age is not None and age >= min_age_days
            r["baseline_target_in_window"] = age is not None and 0 <= age <= max_age_days
            if age is not None and min_age_days <= age <= max_age_days:
                mature.append(r)
        mature.sort(key=lambda r: (date(r["published_at"]), str(r["content_id"])), reverse=True)
        for r in members:
            pool = [p for p in mature if p["content_id"] != r["content_id"]][:max_samples]
            samples = [p for p in pool if number(p.get(metric))]
            median = statistics.median([p[metric] for p in samples]) if samples else None
            reason = ("insufficient_samples" if len(samples) < min_samples else
                      "zero_baseline" if median == 0 else
                      "missing_target_metric" if not number(r.get(metric)) else None)
            r["baseline"] = {"metric": metric, "median": median, "ratio": None if reason else r[metric] / median,
                "reason": reason, "candidate_count": len(pool), "sample_count": len(samples),
                "missing_metric_count": len(pool) - len(samples),
                "sample_ids": [p["content_id"] for p in samples],
                "sample_values": [p[metric] for p in samples],
                "sample_published_at": [p["published_at"] for p in samples],
                "as_of": reference.isoformat(), "group": list(group_key(r))}
    for r in result["records"]:
        if not group_key(r):
            r["baseline"] = {"metric": None, "median": None, "ratio": None,
                "reason": "missing_group_identity", "sample_count": 0, "sample_ids": [], "sample_values": [],
                "missing_fields": [k for k in result["baseline_policy"]["group_fields"] if not r.get(k)]}
    return result

def select_comparisons(payload):
    groups = defaultdict(list)
    for r in payload.get("records", []):
        if group_key(r): groups[group_key(r)].append(r)
    selections = []
    for key, members in groups.items():
        ranked = [r for r in members if number(r.get("baseline", {}).get("ratio"))
                  and r.get("baseline_target_mature") is True and r.get("baseline_target_in_window") is True]
        ranked.sort(key=lambda r: (-r["baseline"]["ratio"], str(r["content_id"])))
        if not ranked or ranked[0]["baseline"]["ratio"] <= 1:
            selections.append({"group": list(key), "status": "insufficient_evidence",
                               "reason": "没有可计算且高于自身基线的成熟作品"})
            continue
        high = ranked[0]
        baseline = high["baseline"]
        ordinary = [r for r in members if r["content_id"] in baseline["sample_ids"]]
        ordinary.sort(key=lambda r: (abs(r[baseline["metric"]] - baseline["median"]), str(r["content_id"])))
        peers = [r for r in payload["records"] if r.get("topic_id") and r["topic_id"] == high.get("topic_id")
                 and r.get("platform") == high["platform"] and r.get("author_id") != high["author_id"]
                 and r.get("content_type") == high["content_type"] and r.get("baseline_target_mature") is True
                 and r.get("baseline_target_in_window") is True]
        peers.sort(key=lambda r: str(r.get("published_at") or ""), reverse=True)
        selections.append({"group": list(key), "status": "selected", "high_id": high["content_id"],
            "ordinary_ids": [r["content_id"] for r in ordinary[:2]],
            "other_author_ids": [r["content_id"] for r in peers[:2]],
            "metric": baseline["metric"], "ordinary_target_median": baseline["median"],
            "selection_reason": "同组中自身倍率最高的成熟作品；普通作品取其基线池中最接近中位数的两条",
            "relevance_condition": "同账号同类型；同选题外部作品只采用显式 topic_id，具体内容相关性仍需原文复核",
            "time_condition": payload["baseline_policy"], "causal_status": "observational"})
    return {"schema_version": 2, "record_type": "comparison_selection", "selections": selections}

def source_index(sources):
    index = {}
    for source in sources:
        sid = source.get("source_id")
        if not sid or sid in index or not isinstance(source.get("text"), str):
            raise DecisionError("来源需要唯一 source_id 和原文 text")
        index[sid] = source
    return index

def validate_citation(citation, sources):
    sid = citation.get("source_id")
    if sid not in sources: raise DecisionError(f"引用来源不存在：{sid}")
    source = sources[sid]
    text = source["text"]
    if citation.get("paragraph_id") is not None:
        paragraphs = {str(p["id"]): p["text"] for p in source.get("paragraphs", [])}
        pid = str(citation["paragraph_id"])
        if pid not in paragraphs: raise DecisionError(f"引用段落不存在：{sid}/{pid}")
        text = paragraphs[pid]
    quote = citation.get("quote")
    if not isinstance(quote, str) or not quote.strip() or quote not in text:
        raise DecisionError(f"引用文字无法回到原文：{sid}")
    if "start_seconds" in citation or "end_seconds" in citation:
        start, end = citation.get("start_seconds"), citation.get("end_seconds")
        if source.get("time_precision") not in {"sentence", "word"} or source.get("alignment_reviewed") is not True:
            raise DecisionError(f"来源没有精确对齐：{sid}")
        if not number(start) or not number(end) or start >= end or not number(source.get("duration_seconds")) or end > source["duration_seconds"]:
            raise DecisionError("引用时间范围无效")
        alignments = source.get("alignments", [])
        if not any(a.get("start_seconds") == start and a.get("end_seconds") == end
                   and quote in a.get("text", "") for a in alignments):
            raise DecisionError("引用时间未对应已复核的对齐片段")
    return True

def _required_text(item, keys):
    for key in keys:
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise DecisionError(f"缺少分析字段：{key}")

def validate_analysis(analysis, sources):
    index = source_index(sources)
    checked = 0
    dimensions = {"topic", "hook", "progression", "proof", "visual", "comments"}
    for comparison in analysis.get("comparisons", []):
        observed = {d.get("dimension") for d in comparison.get("dimensions", [])}
        if observed != dimensions: raise DecisionError("作品对照需覆盖六个维度，缺材料的维度显式标 unknown")
        for item in comparison["dimensions"]:
            _required_text(item, ["observation", "testable_change"])
            if not item.get("alternative_explanations"): raise DecisionError("缺少其他可能解释")
            citations = item.get("citations", [])
            if not citations and item.get("status") != "unknown": raise DecisionError("观察结论没有原文证据")
            for citation in citations:
                validate_citation(citation, index); checked += 1
            if item.get("pattern_type") == "repeated":
                cited_sources = [index[c["source_id"]] for c in citations]
                identities = {(s.get("platform"), s.get("content_id")) if s.get("content_id")
                              else (None, digest(s["text"])) for s in cited_sources}
                if len(identities) < 2:
                    raise DecisionError("重复规律需要至少两条独立内容")
    operations = {"keep", "add", "delete", "rewrite", "replace_example", "split", "merge", "reorder"}
    for item in analysis.get("evolution", []):
        if item.get("operation") not in operations: raise DecisionError("演化操作无效")
        _required_text(item, ["logic", "expression", "fact_change", "recommendation"])
        left, right = item.get("from", []), item.get("to", [])
        op = item["operation"]
        if op != "add" and not left or op != "delete" and not right:
            raise DecisionError("演化判断缺少前后引用")
        if op == "split" and len(right) < 2 or op == "merge" and len(left) < 2:
            raise DecisionError("拆段或合段需要多段引用")
        for citation in left + right:
            validate_citation(citation, index); checked += 1
    for section in analysis.get("draft_sections", []):
        _required_text(section, ["id", "text", "borrowed_logic", "expression_change"])
        for c in section.get("references", []) + section.get("own_facts", []):
            validate_citation(c, index); checked += 1
        if not section.get("references") and not section.get("own_facts") and not section.get("material_gap"):
            raise DecisionError("写稿段落需要来源、本人事实或明确的材料缺口")
    return {"status": "valid", "citations_checked": checked, "analysis_hash": digest(analysis),
            "sources_hash": digest(sources), "semantic_judgment": "agent_supplied_not_programmatically_proven"}

def comment_key(row):
    return (row.get("platform"), str(row.get("content_id")), str(row.get("comment_id")))

def aggregate_questions(comments, analysis, sources=()):
    rows = {comment_key(r): r for r in comments.get("records", []) if r.get("comment_id")}
    src = source_index(sources)
    results = []
    for question in analysis.get("questions", []):
        _required_text(question, ["id", "question"])
        if question.get("kind") == "claim_keyword": continue
        if question.get("kind") != "genuine_question": raise DecisionError("问题类别必须由 Agent 明确标注")
        members = []
        for ref in question.get("members", []):
            key = comment_key(ref)
            if key not in rows: raise DecisionError("问题引用的评论不存在")
            r = rows[key]
            if r.get("primary_category") in {"领取口令", "claim_keyword"}:
                continue
            if r.get("is_noise") or r.get("is_reply") is not False: continue
            if key not in [comment_key(m) for m in members]: members.append(r)
        if not members: continue
        reviews = {comment_key(r): r for r in question.get("thread_reviews", [])}
        statuses, evidence = [], []
        for member in members:
            review = reviews.get(comment_key(member), {})
            status = review.get("status", "unknown")
            if status not in {"answered", "partial", "unanswered_in_sample", "unknown"}:
                raise DecisionError("回答状态无效")
            replies = [r for r in rows.values() if r.get("is_reply") is True
                and r.get("platform") == member.get("platform") and r.get("content_id") == member.get("content_id")
                and str(r.get("root_comment_id")) == str(member["comment_id"])]
            ids = {str(r["comment_id"]) for r in replies}
            cited = set(map(str, review.get("evidence_comment_ids", [])))
            if not cited <= ids: raise DecisionError("回复证据不属于该问题线程")
            if status in {"answered", "partial"} and not cited:
                raise DecisionError("有效回答判断需要具体回复")
            if status != "unknown" and not review.get("reason"): raise DecisionError("回答判断缺少理由")
            reported, fetched = member.get("reply_count_reported"), len(replies)
            complete = (member.get("reply_coverage") == "complete" and number(reported)
                        and fetched >= reported)
            if not complete: status = "unknown"
            statuses.append(status)
            evidence.append({"platform": member.get("platform"), "content_id": member["content_id"],
                "comment_id": member["comment_id"], "quote": member.get("comment_text"),
                "source_url": member.get("source_url"), "status": status, "reply_coverage": member.get("reply_coverage", "unknown"),
                "reported_replies": reported, "fetched_replies": fetched,
                "evidence_comment_ids": sorted(cited), "reason": review.get("reason"),
                "evidence_comments": [{"comment_id": r["comment_id"], "quote": r.get("comment_text"),
                    "is_content_author": r.get("is_content_author")} for r in replies if str(r["comment_id"]) in cited]})
        video_status = question.get("video_addressed", "unknown")
        if video_status not in {"addressed", "partial", "not_addressed", "unknown"}:
            raise DecisionError("原视频覆盖状态无效")
        citations = question.get("video_citations", [])
        if video_status != "unknown" and not citations:
            raise DecisionError("原视频是否讲到需要原文证据")
        for c in citations: validate_citation(c, src)
        if video_status == "not_addressed":
            reviewed = question.get("video_review", {})
            if reviewed.get("full_transcript_reviewed") is not True or not reviewed.get("reason"):
                raise DecisionError("未讲到的判断需要复核完整逐字稿并说明范围")
            if not all(src[c["source_id"]].get("text_coverage") == "full" for c in citations):
                raise DecisionError("部分原文不能证明整条视频未讲到")
        opportunity = question.get("opportunity")
        if opportunity:
            _required_text(opportunity, ["audience", "angle"])
            if not opportunity.get("evidence") or "material_gaps" not in opportunity:
                raise DecisionError("内容机会缺少已有证据或材料缺口")
        results.append({"id": question["id"], "question": question["question"],
            "occurrences": len(members), "video_count": len({(m["platform"], m["content_id"]) for m in members}),
            "answer_counts": dict(Counter(statuses)), "video_addressed": video_status,
            "video_citations": citations, "video_review": question.get("video_review"),
            "representatives": evidence, "opportunity": opportunity})
    return {"schema_version": 2, "record_type": "question_research", "questions": results,
        "coverage": comments.get("summary", {}), "denominator": "去重、非噪声且已知为顶层的真实问题评论；领取口令不计入",
        "semantic_judgment": "agent_supplied"}

def exact_matches(left, right, min_chars=8):
    def normalized(text):
        pairs = [(c, i) for i, c in enumerate(text) if "\u4e00" <= c <= "\u9fff" or c.isdigit()]
        return "".join(c for c, _ in pairs), [i for _, i in pairs]
    a, ai = normalized(left); b, bi = normalized(right)
    result = []
    for m in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        if m.size >= min_chars:
            result.append({"left_start": ai[m.a], "left_end": ai[m.a + m.size - 1] + 1,
                "right_start": bi[m.b], "right_end": bi[m.b + m.size - 1] + 1,
                "characters": m.size})
    return result

def refresh_section(section, sources):
    section["exact_matches"] = [{"source_id": ref["source_id"], "matches": exact_matches(ref["quote"], section["mine"])}
                                 for ref in section.get("references", [])]
    section["analysis_status"] = "reviewed" if isinstance(section.get("reviewed_text"), str) and section["reviewed_text"] == section["mine"] else "needs_review"

def validate_workbench(state):
    if state.get("schema_version") != 2: raise DecisionError("写稿页需要 schema_version 2")
    index = source_index(state.get("sources", []))
    seen = set()
    for section in state.get("sections", []):
        sid = section.get("id")
        if not sid or sid in seen: raise DecisionError("段落 id 缺失或重复")
        seen.add(sid)
        if not isinstance(section.get("mine"), str) or not isinstance(section.get("note", ""), str):
            raise DecisionError("稿件与批注必须是文字")
        for ref in section.get("references", []): validate_citation(ref, index)
        for group in section.get("semantic_groups", []):
            for ref in group.get("sources", []): validate_citation(ref, index)
            if section.get("analysis_status") == "reviewed" and group.get("mine") not in section["mine"]:
                raise DecisionError("已复核语义标注不在当前稿件中")
    return True

def render_workbench(state, template=None):
    validate_workbench(state)
    template = Path(template) if template else Path(__file__).resolve().parents[1] / "assets/writing-template.html"
    page = template.read_text(encoding="utf-8")
    serialized = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return page.replace("__WORKBENCH_STATE__", serialized)

def import_t016(path):
    path = Path(path)
    page = path.read_text(encoding="utf-8")
    def embedded(name):
        match = re.search(r'<script\s+id=["\']' + re.escape(name) + r'["\'][^>]*>([\s\S]*?)</script>', page)
        if not match: raise DecisionError(f"缺少 {name}")
        return json.loads(match.group(1))
    data, comparison = embedded("t016-data"), embedded("t016-comparison")
    sources = []
    for i, origin in enumerate(data["sources"]):
        paragraphs = [{"id": str(s["id"]), "text": s["refs"][i]} for s in data["sections"]]
        meta = Path(origin).parents[2] / "笔记信息.md"
        meta_text = meta.read_text(encoding="utf-8") if meta.is_file() else ""
        author = re.search(r"\| (?:作者昵称|达人昵称) \| ([^\n]+?) \|", meta_text)
        label = author.group(1).strip() if author else Path(origin).parents[2].name
        sources.append({"source_id": f"source-{i + 1}", "title": label,
            "text": "\n\n".join(p["text"] for p in paragraphs), "paragraphs": paragraphs,
            "time_precision": "unknown", "original_file": origin,
            "original_file_sha256": hashlib.sha256(Path(origin).read_bytes()).hexdigest() if Path(origin).is_file() else None,
            "representation": "T016 对照页中的原文分段；原始校正版文件另存来源，不推算时间"})
    state = {"schema_version": 2, "record_type": "writing_workbench", "task_id": data["content_id"] + "-independent",
        "title": "T016 · 研究证据与写稿", "revision": data["revision"], "updated_at": data.get("updatedAt"),
        "sources": sources, "sections": [], "history": [], "profile": {},
        "import_provenance": {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_revision": data["revision"], "comparison_review_history": comparison.get("reviewHistory", [])}}
    for old in data["sections"]:
        sid = str(old["id"])
        section = {"id": sid, "title": old["title"], "mine": old["mine"], "note": old.get("note", ""),
            "baseline": old.get("baseline"), "locked": False, "history": deepcopy(old.get("history", [])),
            "reference_history": deepcopy(old.get("referenceHistory", [])),
            "references": [{"source_id": f"source-{i + 1}", "paragraph_id": sid, "quote": text} for i, text in enumerate(old["refs"]) if text],
            "reviewed_text": comparison.get("reviewedMine", {}).get(sid),
            "analysis_status": "reviewed" if comparison.get("reviewedMine", {}).get(sid) == old["mine"] else "needs_review",
            "semantic_groups": [], "borrowed_logic": "", "own_facts": [], "expression_change": ""}
        for g in comparison.get("groups", []):
            if str(g["section"]) != sid: continue
            section["semantic_groups"].append({"id": g["id"], "color": g["color"], "label": g["label"],
                "mine": g["mine"], "comment": g.get("comment", ""), "sources": [
                    {"source_id": f"source-{r['author'] + 1}", "paragraph_id": str(r["section"]), "quote": r["text"]}
                    for r in g["sources"]]})
        refresh_section(section, sources)
        state["sections"].append(section)
    validate_workbench(state)
    return state

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("baselines", "select", "validate-analysis", "questions", "import-t016", "render-writing"):
        p = subs.add_parser(name)
        p.add_argument("--input", required=True, type=Path)
        p.add_argument("--output", required=True, type=Path)
        if name in {"validate-analysis", "questions"}: p.add_argument("--sources", required=True, type=Path)
        if name == "questions": p.add_argument("--analysis", required=True, type=Path)
        if name == "baselines": p.add_argument("--as-of")
    args = parser.parse_args(argv)
    try:
        if args.command == "import-t016": output = import_t016(args.input)
        else:
            value = read_json(args.input)
            if args.command == "baselines": output = calculate_baselines(value, args.as_of)
            elif args.command == "select": output = select_comparisons(value)
            elif args.command == "validate-analysis": output = validate_analysis(value, read_json(args.sources))
            elif args.command == "questions": output = aggregate_questions(value, read_json(args.analysis), read_json(args.sources))
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x", encoding="utf-8") as handle: handle.write(render_workbench(value))
                print(json.dumps({"ok": True, "output": args.output.name})); return 0
        write_new(args.output, output)
    except (DecisionError, OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"research_decisions: {exc}\n")
    print(json.dumps({"ok": True, "output": args.output.name}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
