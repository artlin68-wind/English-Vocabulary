#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_images.py — Phase 2:建置時抓「免費授權」圖片並打包(執行期離線可看)。

單字圖(imageWord):
  1) Wikipedia 摘要圖(en.wikipedia REST summary 的 thumbnail;多為 Commons CC/PD,乾淨、品質佳)
  2) --openverse 時,查無/歧義才用 Openverse(只取寬鬆授權且限定博物館/Wikimedia 乾淨來源)
  3) 仍無(多為抽象字)→ 留白(null)
例句情境圖(imageSentence):
  由例句抽一個關鍵名詞當查詢字,同樣 Wikipedia 優先(--openverse 才補 Openverse);查無 → 留白。
  預設只用 Wikipedia:乾淨無浮水印、快、穩定;抽象/查無者留白(符合「找不到貼切圖允許留白」)。

所有圖片縮到最長邊 <= MAXW、存成 JPEG(控制離線體積),路徑寫回 JSON。
另產 images/credits.json 記錄每張圖的來源/授權/作者/原始頁,供 README 標註。

特性:斷點續跑(已存在的圖跳過)、Wikimedia/Openverse 禮貌限速、進度輸出。

用法:
  python scripts/gen_images.py --book G1-S1
  python scripts/gen_images.py --book G1-S1 --only word --limit 12
  python scripts/gen_images.py --book G1-S1 --only sentence
"""
import argparse
import io
import json
import os
import re
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "index.json")
WIKI_API = "https://en.wikipedia.org/w/api.php"       # 批次 pageimages(一次最多 50 標題)
WIKI_PAGE = "https://en.wikipedia.org/wiki/{}"
OPENVERSE = "https://api.openverse.org/v1/images/"
# 只接受可自由散布的授權(教育用途仍建議 README 標註)
OK_LICENSES = {"cc0", "pdm", "by", "by-sa"}
# 只取「乾淨」來源(博物館 / Wikimedia),避免商用圖庫的浮水印與雜圖
CLEAN_SOURCES = "wikimedia,met,smithsonian,clevelandmuseum,rawpixel,statensmuseum,brooklynmuseum,nypl"
MAXW = 512           # 縮圖最長邊(控制離線體積)
JPEG_Q = 80

try:
    import requests
except ImportError:
    sys.exit("缺少 requests,請先執行:pip install requests")
try:
    from PIL import Image
except ImportError:
    sys.exit("缺少 Pillow,請先執行:pip install Pillow")

_session = requests.Session()
_session.headers.update({"User-Agent": "vocab-app-build/1.0 (educational; images)"})

# ---- 禮貌限速(所有呼叫共用) ----
_rate_lock = threading.Lock()
_last = [0.0]
_GAP = 0.25


def _throttle():
    with _rate_lock:
        w = _GAP - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()


def _get(url, **kw):
    _throttle()
    for attempt in range(3):
        try:
            r = _session.get(url, timeout=15, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (429,) or r.status_code >= 500:
                time.sleep(1.2 * (attempt + 1)); continue
            return r
        except requests.RequestException:
            time.sleep(1.0 * (attempt + 1))
    return None


# ---------- 來源 ----------
def wiki_images_batch(queries):
    """一次查多個標題的代表圖(MediaWiki pageimages,最多 50/次、跟隨重導)。
    回傳 { 原始查詢字(小寫): (img_url, credit) }(查無者不放入)。"""
    out = {}
    uniq = list({q.strip(): None for q in queries if q and q.strip()})
    for i in range(0, len(uniq), 50):
        chunk = uniq[i:i + 50]
        r = _get(WIKI_API, params={
            "action": "query", "format": "json", "redirects": "1",
            "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": str(MAXW),
            "titles": "|".join(chunk),
        })
        if not r or r.status_code != 200:
            continue
        try:
            q = r.json().get("query", {})
        except ValueError:
            continue
        # 建立 原輸入 → 正規化/重導後標題 的對照
        alias = {}
        for n in q.get("normalized", []):
            alias[n["from"]] = n["to"]
        for rd in q.get("redirects", []):
            alias[rd["from"]] = rd["to"]

        def resolve(t):
            seen = 0
            while t in alias and seen < 5:
                t = alias[t]; seen += 1
            return t

        title2thumb = {}
        for _, pg in q.get("pages", {}).items():
            th = (pg.get("thumbnail") or {}).get("source")
            if th:
                title2thumb[pg.get("title", "")] = th
        for orig in chunk:
            th = title2thumb.get(resolve(orig))
            if th:
                credit = {"source": "Wikipedia", "title": resolve(orig),
                          "page": WIKI_PAGE.format(resolve(orig).replace(" ", "_")),
                          "license": "見 Wikimedia Commons 檔案頁"}
                out[orig.lower()] = (th, credit)
    return out


def openverse_image(query, clean=True):
    """回傳 (img_url, credit) 或 (None, None);只取寬鬆授權。
    clean=True 時再限定乾淨來源(博物館 / Wikimedia),避免浮水印雜圖。"""
    params = {"q": query, "page_size": 5, "license": ",".join(OK_LICENSES),
              "mature": "false"}
    if clean:
        params["source"] = CLEAN_SOURCES
    r = _get(OPENVERSE, params=params)
    if not r or r.status_code != 200:
        return None, None
    try:
        results = r.json().get("results", [])
    except ValueError:
        return None, None
    for it in results:
        url = it.get("url") or it.get("thumbnail")
        if not url:
            continue
        credit = {"source": "Openverse/" + (it.get("source") or ""),
                  "title": it.get("title", query),
                  "author": it.get("creator", ""),
                  "page": it.get("foreign_landing_url", ""),
                  "license": f"{it.get('license','')} {it.get('license_version','')}".strip()}
        return url, credit
    return None, None


# ---------- 下載 + 縮圖 ----------
def save_image(url, dest):
    r = _get(url)
    if not r or r.status_code != 200 or not r.content or len(r.content) < 800:
        return False
    try:
        im = Image.open(io.BytesIO(r.content))
        im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, MAXW / max(w, h))
        if scale < 1.0:
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        tmp = dest + ".part"
        im.save(tmp, "JPEG", quality=JPEG_Q, optimize=True)
        os.replace(tmp, dest)
        return True
    except Exception:
        return False


# ---------- 例句關鍵字 ----------
STOP = set("""a an the this that these those of in on at to for from with without and or but
we you they he she it i me him her them us my your his its our their be am is are was were been
being have has had do does did will would can could should may might must not no as by so if then
than too very much many more most some any all each every one two three there here what which who
whom whose when where why how up down out over under again further once about into off""".split())


# 常見動詞/非名詞尾綴,盡量避開當情境主詞
_VERBISH = ("ed", "ing", "ly", "es")


def sentence_keywords(sentence, headword):
    """挑一個最適合當情境圖查詢的名詞:偏好句中較後、非動詞/副詞的內容字
    (英語受詞名詞多在句末),回傳單一關鍵字;抽不到回 None。"""
    words = re.findall(r"[A-Za-z]+", sentence)
    content = [w for w in words
               if w.lower() not in STOP and len(w) > 2 and w.lower() != headword.lower()]
    if not content:
        return None
    # 由句末往前找「不像動詞/副詞」的字當名詞
    for w in reversed(content):
        if not w.lower().endswith(_VERBISH):
            return w
    # 全都像動詞就取最長的
    return max(content, key=len)


# ---------- 主流程 ----------
def process(bookfile, args):
    full = os.path.join(ROOT, bookfile)
    data = json.load(open(full, encoding="utf-8"))
    words = data["words"]
    if args.limit:
        words = words[: args.limit]

    wdir = os.path.join(ROOT, "images", "word")
    sdir = os.path.join(ROOT, "images", "sentence")
    os.makedirs(wdir, exist_ok=True)
    os.makedirs(sdir, exist_ok=True)
    credits_path = os.path.join(ROOT, "images", "credits.json")
    credits = json.load(open(credits_path, encoding="utf-8")) if os.path.exists(credits_path) else {}

    do_w = args.only in (None, "word")
    do_s = args.only in (None, "sentence")
    st = {"w_ok": 0, "w_blank": 0, "s_ok": 0, "s_blank": 0, "skip": 0}

    # 1) 收集待處理任務(略過已存在的圖檔),並記錄每筆的查詢字
    tasks = []   # (word_obj, kind, query, dest, rel)
    for w in words:
        wid = w["id"]
        if do_w:
            dest = os.path.join(wdir, f"{wid}.jpg"); rel = f"images/word/{wid}.jpg"
            if os.path.exists(dest):
                w["imageWord"] = rel; st["skip"] += 1
            else:
                tasks.append((w, "word", w["lookup"], dest, rel))
        if do_s:
            dest = os.path.join(sdir, f"{wid}.jpg"); rel = f"images/sentence/{wid}.jpg"
            ex = (w.get("example") or "").strip()
            if os.path.exists(dest):
                w["imageSentence"] = rel; st["skip"] += 1
            elif ex and ex != "—":
                kw = sentence_keywords(ex, w["word"])
                if kw:
                    tasks.append((w, "sentence", kw, dest, rel))
                else:
                    w["imageSentence"] = None
            else:
                w["imageSentence"] = None

    print(f"  待抓 {len(tasks)} 張(略過已存在 {st['skip']})", flush=True)

    # 2) 批次向 Wikipedia 解析所有查詢字 → 圖片 URL(一次 50 標題,快又不易被限速)
    all_queries = [t[2] for t in tasks]
    url_map = wiki_images_batch(all_queries)   # {query.lower(): (url, credit)}
    print(f"  Wikipedia 命中 {len(url_map)} 個查詢字", flush=True)

    # 3) 逐筆下載(相同 URL 只下載一次),寫檔 + 回填 JSON
    downloaded = {}   # url -> local first dest(供相同圖複用)
    n = 0
    for (w, kind, query, dest, rel) in tasks:
        pair = url_map.get(query.lower())
        if not pair and args.openverse:
            url2, credit2 = openverse_image(query, clean=True)
            if url2:
                pair = (url2, credit2)
        ok = False
        if pair:
            url, credit = pair
            if url in downloaded and os.path.exists(downloaded[url]):
                import shutil
                try:
                    shutil.copyfile(downloaded[url], dest); ok = True
                except OSError:
                    ok = False
            else:
                ok = save_image(url, dest)
                if ok:
                    downloaded[url] = dest
            if ok:
                credits[rel] = credit
        if kind == "word":
            w["imageWord"] = rel if ok else None
            st["w_ok" if ok else "w_blank"] += 1
        else:
            w["imageSentence"] = rel if ok else None
            st["s_ok" if ok else "s_blank"] += 1
        n += 1
        if n % 50 == 0:
            print(f"  下載 {n}/{len(tasks)}  單字圖 {st['w_ok']} / 情境圖 {st['s_ok']}", flush=True)
            _flush(data, full, credits, credits_path)

    _flush(data, full, credits, credits_path)
    print(f"[{data['meta']['book']}] 單字圖 OK {st['w_ok']} / 留白 {st['w_blank']} | "
          f"情境圖 OK {st['s_ok']} / 留白 {st['s_blank']} | 略過 {st['skip']}")


def _flush(data, full, credits, credits_path):
    json.dump(data, open(full, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(credits, open(credits_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book")
    ap.add_argument("--only", choices=["word", "sentence"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--openverse", action="store_true",
                    help="Wikipedia 查無時,額外用 Openverse 乾淨來源補圖(覆蓋率較高、稍慢)")
    args = ap.parse_args()
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    books = manifest["books"]
    if args.book:
        books = [b for b in books if b["book"] == args.book]
        if not books:
            sys.exit(f"manifest 找不到 book: {args.book}")
    for b in books:
        print(f"== 產生圖片 {b['book']} ({b['file']}) ==", flush=True)
        process(b["file"], args)


if __name__ == "__main__":
    main()
