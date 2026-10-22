#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_audio.py — 建置時預先產生單字/例句音檔(執行期不需任何 API / KEY,可離線)。

單字發音:預設用 edge-tts 神經語音(穩定、100% 覆蓋、音質自然、iOS 保證支援)。
          加 --human 則優先抓 Wikimedia Commons 真人母語錄音(En-us / Lingua Libre),
          用內附 ffmpeg 轉成 mp3,查無者退回 TTS,並在 JSON 以 audioWordSource
          標記 human / tts,方便日後把 TTS 版換成真人版。
例句發音:逐例句用 edge-tts(微軟 Neural 語音,免費、無需 KEY、音質自然)合成。

輸出:audio/word/{id}.mp3、audio/sentence/{id}-{n}.mp3(n 為例句序號;mono mp3,iOS Safari 保證支援)。
JSON 寫回:audioWord / audioWordSource / examples[i].audio。

特性:斷點續跑(已存在的音檔跳過、不重產)、進度輸出、對外部來源重試 + 速率控制。

用法:
  python scripts/gen_audio.py                    # 所有書、單字+例句
  python scripts/gen_audio.py --book G1-S1
  python scripts/gen_audio.py --only word        # 只做單字音
  python scripts/gen_audio.py --only sentence     # 只做例句音
  python scripts/gen_audio.py --limit 20          # 只跑前 20 筆(測試用)
  python scripts/gen_audio.py --human             # 單字優先抓 Commons 真人錄音(較慢)
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "index.json")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

VOICE = "en-US-EmmaNeural"   # 例句 + 單字 TTS(年輕清楚的女聲);可用 --voice 覆寫
WORD_VOICE = "en-US-EmmaNeural"

try:
    import edge_tts
except ImportError:
    sys.exit("缺少 edge-tts,請先執行:pip install edge-tts")
try:
    import requests
except ImportError:
    sys.exit("缺少 requests,請先執行:pip install requests")


# ---------- 單字真人錄音(Wikimedia Commons / 字典) ----------
_session = requests.Session()
_session.headers.update({"User-Agent": "vocab-app-build/1.0 (educational; contact:local)"})

# ffmpeg(imageio-ffmpeg 內附),把 Commons 的 ogg/wav 真人錄音轉成 iOS 保證支援的 mp3
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = None

import subprocess


# Wikimedia API 禮貌:全域限速(所有執行緒共用),避免並發打爆被 throttle
import threading
_rate_lock = threading.Lock()
_last_call = [0.0]
_MIN_GAP = 0.8  # 秒(Wikimedia API 禮貌間隔,避免爆量被 throttle)


def _throttle():
    with _rate_lock:
        now = time.time()
        wait = _MIN_GAP - (now - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def _commons_query(params):
    p = {"format": "json", "maxlag": "5"}
    p.update(params)
    for attempt in range(4):
        _throttle()
        try:
            r = _session.get(COMMONS_API, params=p, timeout=15)
            if r.status_code == 200:
                j = r.json()
                # maxlag / throttle 時 API 會回 error,退避重試
                if isinstance(j, dict) and j.get("error", {}).get("code") in (
                        "maxlag", "ratelimited"):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return j
            if r.status_code in (429,) or r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                continue
        except requests.RequestException:
            time.sleep(1.0 * (attempt + 1))
    return None


def _fileurl_for_title(title):
    """title 形如 'File:En-us-ancient.ogg' → 直接媒體 URL,不存在回 None。"""
    j = _commons_query({"action": "query", "titles": title,
                        "prop": "imageinfo", "iiprop": "url|mime"})
    if not j:
        return None
    pages = j.get("query", {}).get("pages", {})
    for _, pg in pages.items():
        if "missing" in pg:
            return None
        for ii in pg.get("imageinfo", []):
            return ii.get("url")
    return None


def find_commons_human_url(word: str):
    """回傳真人英語發音檔的媒體 URL;查無回 None。
    以一次搜尋為主(省 API 呼叫):優先 Lingua Libre (LL-Q1860 eng)、
    其次 Wiktionary 經典 En-us 錄音,取檔名字尾精確吻合單字者。"""
    w = word.strip()
    # 1) Wiktionary 經典 En-us 美式錄音(直接檔名,最準)
    u = _fileurl_for_title(f"File:En-us-{w}.ogg")
    if u:
        return u
    # 2) Lingua Libre 群眾錄音:搜尋後取檔名字尾精確吻合單字者
    j = _commons_query({"action": "query", "list": "search",
                        "srsearch": f"LL-Q1860 (eng)-{w}",
                        "srnamespace": "6", "srlimit": "25"})
    if not j:
        return None
    ll_pat = re.compile(r"LL-Q1860 \(eng\)-.+-%s\.(wav|ogg|flac)$" % re.escape(w),
                        re.IGNORECASE)
    for hit in j.get("query", {}).get("search", []):
        title = hit.get("title", "")
        if ll_pat.search(title):
            u = _fileurl_for_title(title)
            if u:
                return u
    return None


def transcode_to_mp3(src_bytes: bytes, dest: str) -> bool:
    """用 ffmpeg 把任意音檔 bytes 轉成 mono 48k mp3。"""
    if not FFMPEG:
        return False
    tmp = dest + ".part"
    try:
        proc = subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
             "-i", "pipe:0", "-ac", "1", "-ar", "24000", "-b:a", "48k",
             "-f", "mp3", tmp],
            input=src_bytes, capture_output=True)
        if proc.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 500:
            os.replace(tmp, dest)
            return True
    except Exception:
        pass
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return False


def fetch_human_word_mp3(word: str, dest: str) -> bool:
    """抓 Commons 真人錄音並轉 mp3 存到 dest;成功回 True。"""
    url = find_commons_human_url(word)
    if not url:
        return False
    try:
        r = _session.get(url, timeout=20)
        if r.status_code == 200 and r.content and len(r.content) > 800:
            return transcode_to_mp3(r.content, dest)
    except requests.RequestException:
        pass
    return False


# ---------- edge-tts 合成 ----------
async def tts_save(text: str, dest: str, voice: str, rate: str = "+0%") -> bool:
    tmp = dest + ".part"
    try:
        comm = edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(tmp)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 500:
            os.replace(tmp, dest)
            return True
    except Exception as ex:
        print(f"    ! TTS 失敗 ({text[:24]}...): {ex}", flush=True)
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return False


# ---------- Piper 離線合成(不需網路 / KEY,免受 edge-tts 端點限制) ----------
# 預設語音模型(可用 --piper-model 覆寫);以 scripts/download 的 lessac medium 為準。
PIPER_MODEL = os.path.join(ROOT, "scripts", "voices", "en_US-lessac-medium.onnx")
_piper_voice = None
_piper_lock = threading.Lock()   # onnxruntime 推論序列化,避免多執行緒競用


def _get_piper(model, config):
    global _piper_voice
    if _piper_voice is None:
        from piper import PiperVoice
        _piper_voice = PiperVoice.load(model, config_path=config)
    return _piper_voice


def _piper_wav_bytes(text, model, config) -> bytes:
    import io
    import wave
    v = _get_piper(model, config)
    buf = io.BytesIO()
    with _piper_lock:
        with wave.open(buf, "wb") as wf:
            v.synthesize_wav(text, wf)
    return buf.getvalue()


def piper_save_sync(text: str, dest: str, model: str, config: str) -> bool:
    """Piper 合成 WAV → 用 ffmpeg 轉 mono mp3 存 dest。成功回 True。"""
    try:
        wav = _piper_wav_bytes(text, model, config)
        if wav and len(wav) > 500:
            return transcode_to_mp3(wav, dest)
    except Exception as ex:
        print(f"    ! Piper 失敗 ({text[:24]}...): {ex}", flush=True)
    return False


async def synth(text: str, dest: str, voice: str, args) -> bool:
    """依引擎合成:--piper 用 Piper(離線);否則 edge-tts。"""
    if args.piper:
        return await asyncio.to_thread(
            piper_save_sync, text, dest, args.piper_model, args.piper_config)
    return await tts_save(text, dest, voice)


# ---------- 主流程 ----------
def save_json_atomic(data, full, retries: int = 5):
    """原子寫入(temp + os.replace)並重試,避免 Windows 偶發的檔案鎖 / EINVAL。"""
    tmp = full + ".tmp"
    for attempt in range(retries):
        try:
            with open(tmp, encoding="utf-8", mode="w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, full)
            return True
        except OSError as ex:
            if attempt == retries - 1:
                print(f"    ! 寫回 JSON 失敗(已重試 {retries} 次): {ex}", flush=True)
            else:
                time.sleep(0.5 * (attempt + 1))
    return False


def rel_audio(kind: str, wid: str, idx=None) -> str:
    """kind='word' → audio/word/{id}.mp3;
       kind='sentence' → audio/sentence/{id}-{n}.mp3(n 為 1-based 例句序號)。"""
    if kind == "sentence" and idx is not None:
        return f"audio/sentence/{wid}-{idx}.mp3"
    return f"audio/{kind}/{wid}.mp3"


async def process_book(bookfile: str, args):
    full = os.path.join(ROOT, bookfile)
    with open(full, encoding="utf-8") as f:
        data = json.load(f)
    words = data["words"]
    if args.limit:
        words = words[: args.limit]

    word_dir = os.path.join(ROOT, "audio", "word")
    sent_dir = os.path.join(ROOT, "audio", "sentence")
    os.makedirs(word_dir, exist_ok=True)
    os.makedirs(sent_dir, exist_ok=True)

    do_word = args.only in (None, "word")
    do_sent = args.only in (None, "sentence")

    sem = asyncio.Semaphore(args.concurrency)
    stats = {"word_dict": 0, "word_tts": 0, "word_fail": 0,
             "sent_ok": 0, "sent_fail": 0, "skip": 0, "n": 0}
    total = len(words)
    lock = asyncio.Lock()

    async def handle(w):
        wid = w["id"]
        lookup = (w.get("lookup") or w.get("word") or "").strip()

        # --- 單字音 ---
        if do_word:
            dest = os.path.join(word_dir, f"{wid}.mp3")
            rel = rel_audio("word", wid)
            if os.path.exists(dest) and os.path.getsize(dest) > 500:
                w["audioWord"] = rel
                w.setdefault("audioWordSource", w.get("audioWordSource") or "cached")
                async with lock:
                    stats["skip"] += 1
            else:
                got = False
                if args.human and lookup:
                    # Commons 真人錄音(同步網路/ffmpeg,丟執行緒避免卡事件迴圈)
                    ok = await asyncio.to_thread(fetch_human_word_mp3, lookup, dest)
                    if ok:
                        w["audioWord"] = rel
                        w["audioWordSource"] = "human"
                        got = True
                        async with lock:
                            stats["word_dict"] += 1
                if not got:
                    ok = await synth(w["word"], dest, args.word_voice, args)
                    if ok:
                        w["audioWord"] = rel
                        w["audioWordSource"] = "piper" if args.piper else "tts"
                        async with lock:
                            stats["word_tts"] += 1
                    else:
                        w["audioWord"] = None
                        w["audioWordSource"] = None
                        async with lock:
                            stats["word_fail"] += 1

        # --- 例句音(逐例句,每句一檔 {id}-{n}.mp3) ---
        if do_sent:
            for idx, ex in enumerate(w.get("examples") or [], start=1):
                en = (ex.get("en") or "").strip()
                if not en or en == "—":
                    ex["audio"] = None
                    continue
                dest = os.path.join(sent_dir, f"{wid}-{idx}.mp3")
                rel = rel_audio("sentence", wid, idx)
                if os.path.exists(dest) and os.path.getsize(dest) > 500:
                    ex["audio"] = rel
                    async with lock:
                        stats["skip"] += 1
                    continue
                ok = await synth(en, dest, args.voice, args)
                if ok:
                    ex["audio"] = rel
                    async with lock:
                        stats["sent_ok"] += 1
                else:
                    ex["audio"] = None
                    async with lock:
                        stats["sent_fail"] += 1

        async with lock:
            stats["n"] += 1
            if stats["n"] % 25 == 0:
                print(f"  {stats['n']}/{total}  dict={stats['word_dict']} "
                      f"tts={stats['word_tts']} sent={stats['sent_ok']} "
                      f"skip={stats['skip']} fail={stats['word_fail']+stats['sent_fail']}",
                      flush=True)

    async def guarded(w):
        async with sem:
            await handle(w)

    # 分批寫回 JSON,確保中途中斷也能續跑
    batch = 60
    for i in range(0, len(words), batch):
        chunk = words[i:i + batch]
        await asyncio.gather(*(guarded(w) for w in chunk))
        save_json_atomic(data, full)

    print(f"[{data['meta']['book']}] 完成 {total} 筆 | "
          f"單字:真人 {stats['word_dict']} / TTS {stats['word_tts']} / 失敗 {stats['word_fail']} | "
          f"例句:OK {stats['sent_ok']} / 失敗 {stats['sent_fail']} | 略過(已存在) {stats['skip']}")


async def process_supplement_book(bookfile: str, args):
    """補充本:為單字 / 各衍生詞 / 片語 / 片語例句產音檔。
    路徑:audioWord=audio/word/{id}.mp3、derivatives[n].audio=audio/word/{id}-d{n}.mp3、
          audioPhrase=audio/word/{id}.mp3、audioExample=audio/sentence/{id}-1.mp3。"""
    full = os.path.join(ROOT, bookfile)
    with open(full, encoding="utf-8") as f:
        data = json.load(f)
    word_dir = os.path.join(ROOT, "audio", "word")
    sent_dir = os.path.join(ROOT, "audio", "sentence")
    os.makedirs(word_dir, exist_ok=True)
    os.makedirs(sent_dir, exist_ok=True)
    st = {"ok": 0, "fail": 0, "skip": 0}

    async def one(text, dest, rel):
        """產一個音檔,回傳 rel(成功)或 None。斷點續跑。"""
        text = (text or "").strip()
        if not text:
            return None
        if os.path.exists(dest) and os.path.getsize(dest) > 500:
            st["skip"] += 1
            return rel
        ok = await synth(text, dest, args.voice, args)
        st["ok" if ok else "fail"] += 1
        return rel if ok else None

    words = data.get("words", [])
    phrases = data.get("phrases", [])
    if args.limit:
        words = words[: args.limit]
        phrases = phrases[: max(0, args.limit - len(words))]

    done = 0
    for w in words:
        wid = w["id"]
        w["audioWord"] = await one(w.get("word"), os.path.join(word_dir, f"{wid}.mp3"),
                                   f"audio/word/{wid}.mp3")
        if w.get("audioWord"):
            w.setdefault("audioWordSource", "piper" if args.piper else "tts")
        for n, d in enumerate(w.get("derivatives", []), start=1):
            d["audio"] = await one(d.get("form"), os.path.join(word_dir, f"{wid}-d{n}.mp3"),
                                   f"audio/word/{wid}-d{n}.mp3")
        done += 1
        if done % 20 == 0:
            print(f"  word {done}/{len(words)}  ok={st['ok']} skip={st['skip']} fail={st['fail']}", flush=True)
            save_json_atomic(data, full)

    for p in phrases:
        pid = p["id"]
        p["audioPhrase"] = await one(p.get("phrase"), os.path.join(word_dir, f"{pid}.mp3"),
                                     f"audio/word/{pid}.mp3")
        p["audioExample"] = await one(p.get("example"), os.path.join(sent_dir, f"{pid}-1.mp3"),
                                      f"audio/sentence/{pid}-1.mp3")
    save_json_atomic(data, full)
    print(f"[{data['meta']['book']}] 補充本完成 | OK {st['ok']} / 略過 {st['skip']} / 失敗 {st['fail']}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", help="只處理指定 book code")
    ap.add_argument("--only", choices=["word", "sentence"], help="只做單字或只做例句")
    ap.add_argument("--limit", type=int, help="只跑前 N 筆(測試)")
    ap.add_argument("--concurrency", type=int, default=6, help="並發數(預設 6)")
    ap.add_argument("--human", action="store_true",
                    help="單字優先抓 Wikimedia Commons 真人錄音(需 ffmpeg,較慢、覆蓋率視網路而定),"
                         "查無退回 TTS。預設關閉:全部用 edge-tts 神經語音(穩定、音質自然)。")
    ap.add_argument("--voice", default=VOICE, help="例句 TTS 語音")
    ap.add_argument("--word-voice", default=WORD_VOICE, help="單字 TTS 退路語音")
    ap.add_argument("--piper", action="store_true",
                    help="改用 Piper 離線 TTS(不需網路/KEY,不受 edge-tts 端點限制)。"
                         "預設語音模型為 scripts/voices/en_US-lessac-medium.onnx。")
    ap.add_argument("--piper-model", default=PIPER_MODEL, help="Piper .onnx 模型路徑")
    ap.add_argument("--piper-config", default=None, help="Piper .onnx.json 設定路徑(預設為模型路徑 + .json)")
    args = ap.parse_args()
    if args.piper_config is None:
        args.piper_config = args.piper_model + ".json"
    if args.piper:
        if not os.path.exists(args.piper_model) or not os.path.exists(args.piper_config):
            sys.exit(f"找不到 Piper 模型:{args.piper_model}(.json)。"
                     f"請先下載,例:python -m piper.download_voices en_US-lessac-medium --data-dir scripts/voices")
        print(f"引擎:Piper(離線)— {os.path.basename(args.piper_model)}")

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    books = manifest["books"]
    if args.book:
        books = [b for b in books if b["book"] == args.book]
        if not books:
            sys.exit(f"manifest 內找不到 book: {args.book}")

    t0 = time.time()
    for b in books:
        print(f"== 產生音檔 {b['book']} ({b['file']}) ==", flush=True)
        if b.get("type") == "supplement":
            await process_supplement_book(b["file"], args)
        else:
            await process_book(b["file"], args)
    print(f"全部完成,耗時 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
