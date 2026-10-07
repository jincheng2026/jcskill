#!/usr/bin/env python3
"""语音转文字引擎（jc-zhuanxie 和其他需要转文字的 Skill 共用）。

主引擎：火山引擎豆包语音「录音文件识别标准版 2.0」，提交任务（submit）后轮询结果（query），
音频以 base64 直接上传。
备用引擎：本机 Qwen3-ASR-1.7B（MLX，Apple Silicon），带 Qwen3-ForcedAligner 字级时间。
火山因额度、开通、鉴权、服务或网络原因失败时自动切到备用；音频本身有问题（空音频、
格式错误、参数错误）时不切换，直接报错。

用法：
  python3 volc_asr.py <媒体文件> --out-prefix <输出前缀> [--review-md]
  python3 volc_asr.py --check
  python3 volc_asr.py <媒体文件> --out-prefix <前缀> --engine local   # 强制只用本地
  环境变量 JC_ASR_ENGINE=auto|volc|local 效果同 --engine，默认 auto

输出（均以 <输出前缀> 开头）：
  .volc.json  接口原始返回与合并结果（毫秒时间已换算为秒）
  .txt        每行一整句的原始识别文本
  .srt        小句字幕（按逗号级标点断开）
  .json       小句 + 字级时间戳：
              [{"i","start","end","text","chars":[[字, 起点秒], ...]}]
  .md         带时间戳的逐句稿（--review-md 时生成）
stdout 打印一行 JSON 摘要。

鉴权：先读环境变量 VOLC_SPEECH_API_KEY，再读 macOS 钥匙串
（service volc-speech-api，account volc；测试时可用环境变量 JC_VOLC_KEYCHAIN_SERVICE 换 service 名）。
不打印密钥。
本地备用引擎的 Python 默认在 ~/.local/share/qwen3-asr/venv/bin/python，可用环境变量
JC_QWEN3_ASR_PYTHON 指定别的位置。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
ENDPOINT = SUBMIT_URL
RESOURCE_ID = "volc.seedasr.auc"
POLL_SECONDS = 3
POLL_TIMEOUT = 60 * 60
KEY_ENV = "VOLC_SPEECH_API_KEY"
KEYCHAIN_ACCOUNT = "volc"
DEFAULT_KEYCHAIN_SERVICE = "volc-speech-api"
CHUNK_SECONDS = 1800          # 单个任务最长 30 分钟，控制上传体积
BOUNDARY_SEARCH = 90          # 在目标切点前后多少秒内找静音
MAX_WORKERS = 3
RETRY_CODES = {"55000031"}    # 服务器繁忙
PENDING_CODES = {"20000001", "20000002"}  # 处理中 / 排队中
SILENT_CODE = "20000003"
DEFAULT_LOCAL_PYTHON = Path.home() / ".local/share/qwen3-asr/venv/bin/python"
LOCAL_PYTHON = Path(os.environ.get("JC_QWEN3_ASR_PYTHON") or DEFAULT_LOCAL_PYTHON).expanduser()
LOCAL_MODEL = "Qwen/Qwen3-ASR-1.7B"
LOCAL_ENGINE = f"local-qwen3-asr ({LOCAL_MODEL}, mlx)"
NO_FALLBACK_CODES = {"45000001", "45000002", "45000151"}  # 参数无效 / 空音频 / 音频格式错误
PUNCT_END = set("。！？!?")
PUNCT_CLAUSE = set("，。！？；：,?!;")  # 字幕／字级稿按这些标点断开（不含 . 和 :，避免拆开 3.5、10:30）


def cjk_or_alnum(text: str) -> str:
    return "".join(re.findall(r"[一-鿿A-Za-z0-9]", text)).lower()


def keychain_service() -> str:
    return os.environ.get("JC_VOLC_KEYCHAIN_SERVICE", "").strip() or DEFAULT_KEYCHAIN_SERVICE


MISSING_KEY_HELP = """缺少火山引擎豆包语音的 API Key。
1. 申请：登录火山引擎控制台，进入「豆包语音」，开通「录音文件识别标准版 2.0」，在「API Key 管理」里创建一个 Key。
   ark- 开头的是火山方舟的 Key，不能用在这里。
2. 保存：请你自己在「终端」里运行下面这行，在密码提示处粘贴 Key 后回车（这里要的不是开机密码，Key 不要发进聊天）：
   security add-generic-password -a {account} -s {service} -U -w
也可以改用环境变量 {env}。"""


def missing_key_message() -> str:
    return MISSING_KEY_HELP.format(account=KEYCHAIN_ACCOUNT, service=keychain_service(), env=KEY_ENV)


def _keychain(*extra: str) -> subprocess.CompletedProcess | None:
    security = shutil.which("security")
    if not security:
        return None   # 不是 macOS，或没有 security 命令
    try:
        return subprocess.run(
            [security, "find-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", keychain_service(), *extra],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def key_source() -> str:
    """只看 Key 在哪，不读取 Key 本身：返回 env / keychain / 空字符串。"""
    if os.environ.get(KEY_ENV, "").strip():
        return "env"
    found = _keychain()   # 不带 -w，只确认条目存在，不取出密码
    if found is not None and found.returncode == 0:
        return "keychain"
    return ""


def load_key() -> str:
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        found = _keychain("-w")
        if found is not None and found.returncode == 0:
            key = found.stdout.strip()
    if not key:
        raise SystemExit(missing_key_message())
    return key


INSTALL_HINT = {
    "ffmpeg": "没找到 ffmpeg。装了 Homebrew 的 Mac 在终端运行 brew install ffmpeg（会同时装上 ffprobe）；"
              "其他系统按 https://ffmpeg.org/download.html 安装，装好后确认终端里能直接运行 ffmpeg。",
}
INSTALL_HINT["ffprobe"] = INSTALL_HINT["ffmpeg"].replace("没找到 ffmpeg", "没找到 ffprobe（ffmpeg 自带）")


def find_tool(name: str) -> str:
    found = shutil.which(name) or f"/opt/homebrew/bin/{name}"
    return found if Path(found).is_file() else ""


def tool(name: str) -> str:
    found = find_tool(name)
    if not found:
        raise SystemExit(INSTALL_HINT.get(name, f"未找到 {name}"))
    return found


def probe_duration(media: Path) -> float:
    out = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(media)],
        capture_output=True, text=True, check=True, timeout=120,
    ).stdout
    value = json.loads(out).get("format", {}).get("duration")
    if value in (None, "N/A") or float(value) <= 0:
        raise RuntimeError("ffprobe 读不到媒体时长")
    return float(value)


def extract_audio(media: Path, target: Path) -> None:
    # aresample async：AAC 顺序解码会比容器时间轴短几秒，不加会导致字级时间整体漂移
    subprocess.run(
        [tool("ffmpeg"), "-v", "error", "-y", "-i", str(media), "-vn",
         "-af", "aresample=async=1:first_pts=0", "-ac", "1", "-ar", "16000",
         "-c:a", "libmp3lame", "-b:a", "48k", str(target)],
        check=True, timeout=60 * 60,
    )


def silences(audio: Path) -> list[tuple[float, float]]:
    """返回 [(静音中点, 静音时长)]。"""
    log = subprocess.run(
        [tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(audio),
         "-af", "silencedetect=noise=-35dB:d=0.35", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60 * 60,
    ).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return [((s + e) / 2, e - s) for s, e in zip(starts, ends)]


def plan_chunks(duration: float, audio: Path) -> list[tuple[float, float]]:
    if duration <= CHUNK_SECONDS + 120:
        return [(0.0, duration)]
    gaps = silences(audio)
    cuts, target = [], CHUNK_SECONDS
    while target < duration - 60:
        near = [g for g in gaps if abs(g[0] - target) <= BOUNDARY_SEARCH and (not cuts or g[0] > cuts[-1] + 60)]
        # 优先最长的停顿，越长越可能是句间停顿；同长时取离目标近的
        cut = max(near, key=lambda g: (round(g[1], 1), -abs(g[0] - target)))[0] if near else target
        cuts.append(cut)
        target = cut + CHUNK_SECONDS
    edges = [0.0, *cuts, duration]
    return list(zip(edges[:-1], edges[1:]))


def cut_chunk(audio: Path, start: float, end: float, target: Path) -> None:
    subprocess.run(
        [tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
         "-i", str(audio), "-c:a", "libmp3lame", "-b:a", "48k", str(target)],
        check=True, timeout=30 * 60,
    )


def _post(url: str, key: str, request_id: str, body: dict) -> tuple[str, str, str]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "X-Api-Key": key,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10 * 60) as resp:
            return (resp.headers.get("X-Api-Status-Code", ""), resp.headers.get("X-Tt-Logid", ""),
                    resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        match = re.search(r'"code":\s*(\d+)', detail)
        return (match.group(1) if match else f"HTTP{exc.code}", exc.headers.get("X-Tt-Logid", ""), detail)


def recognize(key: str, audio: Path) -> dict:
    body = {
        "user": {"uid": "jc-zhuanxie"},
        "audio": {"data": base64.b64encode(audio.read_bytes()).decode(), "format": "mp3"},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": False,   # 不做顺滑：保留口语、重复
            "show_utterances": True,
        },
    }
    last_error, code = "", ""
    for attempt in range(4):
        request_id = str(uuid.uuid4())
        try:
            code, logid, text = _post(SUBMIT_URL, key, request_id, body)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = f"提交网络错误：{exc}"
            time.sleep(3 * (attempt + 1))
            continue
        if code != "20000000":
            last_error = f"提交失败 code={code} logid={logid} {text[:300]}"
            if code in RETRY_CODES or code.startswith("HTTP5"):
                time.sleep(3 * (attempt + 1))
                continue
            break
        deadline = time.time() + POLL_TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL_SECONDS)
            try:
                code, logid, text = _post(QUERY_URL, key, request_id, {})
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                continue
            if code in PENDING_CODES:
                continue
            if code == "20000000":
                return {"status": code, "logid": logid, "request_id": request_id, "response": json.loads(text)}
            if code == SILENT_CODE:
                return {"status": code, "logid": logid, "request_id": request_id,
                        "response": {"result": {"text": "", "utterances": []}}}
            last_error = f"查询失败 code={code} logid={logid} {text[:300]}"
            break
        else:
            last_error = f"等待结果超时（{POLL_TIMEOUT} 秒） request_id={request_id}"
        if code not in RETRY_CODES:
            break
        time.sleep(3 * (attempt + 1))
    raise VolcError(f"火山转写失败：{last_error}", code)


class VolcError(RuntimeError):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


def local_available() -> bool:
    return LOCAL_PYTHON.is_file()


def recognize_local(audio: Path) -> dict:
    """本机 Qwen3-ASR：整段音频一次处理（库内部按低能量点切 30 秒块），返回与火山相同的结构。"""
    if not local_available():
        raise RuntimeError(f"本地备用引擎未安装：{LOCAL_PYTHON}（安装方法见 jc-zhuanxie 的 SKILL.md）")
    with tempfile.TemporaryDirectory(prefix="qwen3-asr-") as out:
        env = dict(os.environ, HF_HUB_DISABLE_PROGRESS_BARS="1")
        cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"
        if (cache / "models--Qwen--Qwen3-ASR-1.7B").is_dir() and (cache / "models--Qwen--Qwen3-ForcedAligner-0.6B").is_dir():
            env["HF_HUB_OFFLINE"] = "1"   # 模型已在本机，不联网
        subprocess.run(
            [str(LOCAL_PYTHON), "-m", "mlx_qwen3_asr", str(audio), "--model", LOCAL_MODEL,
             "--language", "Chinese", "--timestamps", "-f", "json", "-o", out,
             "--quiet", "--no-progress"],
            check=True, timeout=6 * 60 * 60, env=env, stderr=subprocess.DEVNULL,
        )
        result = json.loads((Path(out) / f"{audio.stem}.json").read_text(encoding="utf-8"))
    segments = result.get("segments") or []
    utterances = []
    for chunk in result.get("chunks") or [{"text": result.get("text", ""), "start": 0, "end": 1e9}]:
        words = [
            {"text": w["text"], "start_time": int(w["start"] * 1000), "end_time": int(w["end"] * 1000)}
            for w in segments if chunk["start"] <= w["start"] < chunk["end"]
        ]
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        utterances.append({
            "text": text,
            "start_time": words[0]["start_time"] if words else int(chunk["start"] * 1000),
            "end_time": words[-1]["end_time"] if words else int(chunk["end"] * 1000),
            "words": words,
        })
    return {"status": "local", "logid": "", "request_id": "",
            "response": {"result": {"text": result.get("text", ""), "utterances": utterances}}}


def split_utterance(utt: dict, offset: float) -> list[dict]:
    """把一个 utterance 按逗号级标点切成小句，每个小句带字级时间和是否句末。"""
    text = str(utt.get("text") or "").strip()
    u_start = offset + utt.get("start_time", 0) / 1000
    u_end = offset + utt.get("end_time", 0) / 1000
    # 字级 token：CJK 多字词均分时长，拉丁/数字词整体作为一个 token
    tokens: list[list] = []
    for w in utt.get("words") or []:
        wt = str(w.get("text") or "")
        if not cjk_or_alnum(wt):
            continue
        ws = offset + w.get("start_time", 0) / 1000
        we = offset + w.get("end_time", 0) / 1000
        pieces = re.findall(r"[一-鿿]|[A-Za-z0-9]+", wt)
        step = (we - ws) / max(1, len(pieces))
        for k, p in enumerate(pieces):
            tokens.append([p, ws + k * step, ws + (k + 1) * step])
    approx = cjk_or_alnum("".join(t[0] for t in tokens)) != cjk_or_alnum(text)
    if approx:
        # 词与句文本对不上（ITN 等），按句文本线性插值，标记为估计值
        pieces = re.findall(r"[一-鿿]|[A-Za-z0-9]+", text)
        step = (u_end - u_start) / max(1, len(pieces))
        tokens = [[p, u_start + k * step, u_start + (k + 1) * step] for k, p in enumerate(pieces)]

    sentences, buf, chars, ti = [], "", [], 0
    for ch in text:
        buf += ch
        if cjk_or_alnum(ch):
            # 拉丁词在 text 中逐字出现，token 是整词：词的最后一个字母到来时再挂上
            if ti < len(tokens):
                tok = tokens[ti]
                consumed = cjk_or_alnum(buf)
                if consumed.endswith(tok[0].lower()):
                    chars.append(tok)
                    ti += 1
        if ch in PUNCT_CLAUSE and chars:
            sentences.append((buf.strip(), chars))
            buf, chars = "", []
    if buf.strip():
        if chars or not sentences:
            sentences.append((buf.strip(), chars))
        else:
            text_prev, chars_prev = sentences[-1]
            sentences[-1] = (text_prev + buf.strip(), chars_prev)
    # 未被挂上的 token 补到最后一句，保证字与文本一致
    if ti < len(tokens) and sentences:
        sentences[-1][1].extend(tokens[ti:])

    out = []
    for idx, (s_text, s_chars) in enumerate(sentences):
        start = s_chars[0][1] if s_chars else u_start
        end = s_chars[-1][2] if s_chars else u_end
        if idx == len(sentences) - 1:
            end = max(end, min(u_end, end + 0.3))
        out.append({"start": round(start, 3), "end": round(end, 3), "text": s_text,
                    "chars": [[c[0], round(c[1], 3)] for c in s_chars], "approx": approx,
                    "sentence_end": idx == len(sentences) - 1 or s_text[-1] in PUNCT_END})
    return out


def merge_clauses(clauses: list[dict]) -> list[dict]:
    """小句合并为整句（遇句末标点或 utterance 结尾断开），供逐句文本使用。"""
    merged, cur = [], None
    for c in clauses:
        if cur is None:
            cur = {"start": c["start"], "end": c["end"], "text": "", "approx": False}
        cur["text"] += c["text"]
        cur["end"] = c["end"]
        cur["approx"] = cur["approx"] or c["approx"]
        if c["sentence_end"]:
            merged.append(cur)
            cur = None
    if cur:
        merged.append(cur)
    for i, s in enumerate(merged, 1):
        s["i"] = i
    return merged


def engine_label(data: dict) -> str:
    label = data["engine"] if data["resource_id"] in data["engine"] else f"{data['engine']} ({data['resource_id']})"
    return label + ("（火山失败后自动切换）" if data.get("fallback_reason") else "")


def ensure_ready() -> None:
    """火山密钥或本地备用引擎至少有一个可用，否则退出。只确认 Key 在哪，不读取 Key。"""
    if not key_source() and not local_available():
        raise SystemExit(missing_key_message())


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def hms(t: float) -> str:
    s = int(t)
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}"


def transcribe(media: Path, workers: int = MAX_WORKERS, engine: str | None = None) -> dict:
    engine = (engine or os.environ.get("JC_ASR_ENGINE") or "auto").lower()
    if engine not in {"auto", "volc", "local"}:
        raise RuntimeError(f"未知引擎：{engine}")
    duration = probe_duration(media)
    with tempfile.TemporaryDirectory(prefix="volc-asr-") as tmp:
        tmpdir = Path(tmp)
        full = tmpdir / "full.mp3"
        extract_audio(media, full)
        fallback_reason = ""
        if engine != "local":
            try:
                return _finish(media, duration, _transcribe_volc(full, duration, tmpdir, workers),
                               "volcengine-doubao-asr", RESOURCE_ID, "")
            except VolcError as exc:
                if engine == "volc" or exc.code in NO_FALLBACK_CODES or not local_available():
                    raise
                fallback_reason = str(exc)
                print(f"火山转写失败，改用本地 Qwen3-ASR：{exc}", file=sys.stderr)
            except SystemExit as exc:   # 缺密钥
                if engine == "volc" or not local_available():
                    raise
                fallback_reason = str(exc)
                print(f"火山不可用，改用本地 Qwen3-ASR：{exc}", file=sys.stderr)
        return _finish(media, duration, [((0.0, duration), recognize_local(full))],
                       LOCAL_ENGINE, LOCAL_MODEL, fallback_reason)


def _transcribe_volc(full: Path, duration: float, tmpdir: Path, workers: int) -> list:
    key = load_key()
    chunks = plan_chunks(duration, full)
    files = []
    for n, (s, e) in enumerate(chunks):
        if len(chunks) == 1:
            files.append(full)
        else:
            part = tmpdir / f"part{n:03d}.mp3"
            cut_chunk(full, s, e, part)
            files.append(part)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda f: recognize(key, f), files))
    return list(zip(chunks, results))


def _finish(media: Path, duration: float, pairs: list, engine_name: str, resource: str, fallback_reason: str) -> dict:
    clauses, raw = [], []
    for (start, end), res in pairs:
        result = res["response"].get("result") or {}
        raw.append({"chunk_start": start, "chunk_end": end, "status": res["status"],
                    "logid": res["logid"], "request_id": res["request_id"], "response": res["response"]})
        for utt in result.get("utterances") or []:
            clauses.extend(split_utterance(utt, start))
    # 时间单调、句间不重叠
    for i, s in enumerate(clauses):
        if i + 1 < len(clauses) and s["end"] > clauses[i + 1]["start"]:
            s["end"] = max(s["start"], clauses[i + 1]["start"])
        if s["end"] - s["start"] < 0.2:   # 零时长小句，字幕播放器会跳过
            limit = clauses[i + 1]["start"] if i + 1 < len(clauses) else s["start"] + 0.2
            s["end"] = round(max(s["end"], min(s["start"] + 0.2, limit)), 3)
    for i, s in enumerate(clauses, 1):
        s["i"] = i
    sentences = merge_clauses(clauses)
    return {
        "engine": engine_name,
        "resource_id": resource,
        "fallback_reason": fallback_reason,
        "source": str(media),
        "duration_seconds": round(duration, 3),
        "chunks": [{"start": round(s, 3), "end": round(e, 3)} for (s, e), _ in pairs],
        "text": "".join(s["text"] for s in sentences),
        "sentences": sentences,   # 整句：逐句文本、复核稿用
        "clauses": clauses,       # 小句＋字级时间：字幕、切片用
        "raw": raw,
    }


def write_outputs(data: dict, prefix: Path, review_md: bool) -> dict:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    sents = data["sentences"]
    clauses = data["clauses"]
    paths = {
        "raw": prefix.with_name(prefix.name + ".volc.json"),
        "txt": prefix.with_name(prefix.name + ".txt"),
        "srt": prefix.with_name(prefix.name + ".srt"),
        "json": prefix.with_name(prefix.name + ".json"),
    }

    def put(path: Path, content: str) -> None:
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    put(paths["raw"], json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    put(paths["txt"], "\n".join(s["text"] for s in sents) + "\n")
    put(paths["srt"], "\n".join(
        f"{s['i']}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n" for s in clauses))
    put(paths["json"], json.dumps(
        [{"i": s["i"], "start": s["start"], "end": s["end"], "text": s["text"], "chars": s["chars"],
          **({"approx": True} if s["approx"] else {})} for s in clauses],
        ensure_ascii=False, separators=(",", ":")))
    if review_md:
        paths["md"] = prefix.with_name(prefix.name + ".md")
        lines = [
            "---",
            f"source: {data['source']}",
            f"engine: {engine_label(data)}",
            f"duration_seconds: {data['duration_seconds']}",
            "---",
            "",
            "# 原始识别（逐句时间戳）",
            "",
        ]
        lines += [f"[{hms(s['start'])}] {s['text']}" for s in sents] or ["未识别到有效语音。"]
        put(paths["md"], "\n".join(lines) + "\n")
    return {k: str(v) for k, v in paths.items()}


def run_check() -> int:
    source = key_source()
    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    local = local_available()
    report = {
        "ok": bool(ffmpeg and ffprobe and (source or local)),
        "volc_key": bool(source),
        "volc_key_source": {"env": f"环境变量 {KEY_ENV}",
                            "keychain": f"macOS 钥匙串（service {keychain_service()}，account {KEYCHAIN_ACCOUNT}）"}.get(source, "没找到"),
        "volc_resource_id": RESOURCE_ID,
        "ffmpeg": ffmpeg or "没找到",
        "ffprobe": ffprobe or "没找到",
        "local_fallback": local,
        "local_python": str(LOCAL_PYTHON),
        "local_model": LOCAL_MODEL,
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    notes = []
    if not source:
        notes.append(missing_key_message())
    if not (ffmpeg and ffprobe):
        notes.append(INSTALL_HINT["ffmpeg"])
    if not local:
        notes.append("本地备用引擎（Qwen3-ASR，只适用 Apple 芯片 Mac）没装；不装也能用火山转写，安装方法见 jc-zhuanxie 的 SKILL.md。")
    if notes:
        print("\n\n".join(notes), file=sys.stderr)
    return 0 if report["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="豆包语音录音文件识别标准版 2.0 转写")
    ap.add_argument("input", nargs="?", type=Path)
    ap.add_argument("--out-prefix", type=Path)
    ap.add_argument("--review-md", action="store_true", help="另写带时间戳的逐句 md")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    ap.add_argument("--engine", choices=["auto", "volc", "local"], help="默认 auto：火山优先，失败转本地")
    ap.add_argument("--check", action="store_true",
                    help="只检查 Key 在不在、ffmpeg/ffprobe 和本地备用引擎，不调用接口、不打印 Key")
    args = ap.parse_args()
    if args.check:
        return run_check()
    if not args.input or not args.out_prefix:
        ap.error("需要 <媒体文件> 和 --out-prefix")
    media = args.input.expanduser().resolve()
    if not media.is_file():
        ap.error(f"媒体不存在：{media}")
    data = transcribe(media, args.workers, args.engine)
    paths = write_outputs(data, args.out_prefix.expanduser().resolve(), args.review_md)
    print(json.dumps({"ok": True, "engine": data["engine"], "fallback_reason": data["fallback_reason"],
                      "sentences": len(data["sentences"]), "clauses": len(data["clauses"]),
                      "text_length": len(data["text"]),
                      "duration_seconds": data["duration_seconds"], "chunks": len(data["chunks"]),
                      "approx_sentences": sum(s["approx"] for s in data["clauses"]), **paths},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"转写失败：{exc}", file=sys.stderr)
        sys.exit(1)
