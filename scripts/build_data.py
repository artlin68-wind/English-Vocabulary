#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_data.py (v2) — 把 Markdown 單字本解析成 data/<book>.json 並更新 data/index.json。

來源 Markdown 格式(見 Level2_單字本_p1-72.md):
  ## 第 N 頁                          → 一頁(unit = 「第 N 頁」, page = N)
  > 📝 ...                            → 該頁的頁級筆記(pageNotes[N],每行一則)
  ### word  `[ipa]`                   → 一個單字;反引號內為音標(含方括號)
  **gloss**                          → 中文解釋(可含多詞性,以 / 分段;動詞三態寫在括號內)
  - 英文例句                          → 例句,下一行縮排為中譯
    中譯
  - 📝 note                          → 該單字的筆記(notes[])

產出每筆 word(v2 schema):
  id / book / page / unit / word / lookup / ipa / ipaRaw / pos[] / gloss /
  verbForms / examples[{en,zh,audio,image}] / notes[] / audioWord / imageWord
頂層另含 meta 與 pageNotes。

安全(冪等):若目標 json 已存在,會以 id 保留既有的音檔/圖片「加值欄位」
  (audioWord/audioWordSource/imageWord 與 examples[i].audio/image),
  只在「文字內容一致」時沿用,避免內容改了還配到舊音檔/圖。

可擴充:任何同格式 md 都能 build 成新的一本;新增一本只在 index.json 加一列,
       既有本 ID 不重編。

用法:
  python scripts/build_data.py --md Level2_單字本_p1-72.md --book G1-S1 --name "高一上 (Level 2)"
  python scripts/build_data.py --md Level2_單字本_p1-72.md --book G1-S1 --check   # 只比對不寫檔
"""
import argparse
import json
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "index.json")

# 重建時從既有檔沿用的「加值欄位」(單字層);例句層的 audio/image 另行處理
ENRICH_WORD_FIELDS = ["audioWord", "audioWordSource", "imageWord"]

# 詞性縮寫白名單(用來從 gloss 取 pos[];可依需要增補)
POS_SET = {"n", "v", "vi", "vt", "adj", "adv", "prep", "conj",
           "pron", "aux", "art", "int", "pl", "abbr"}
POS_TOKEN_RE = re.compile(r"([A-Za-z]+)\.")
# 單一方括號音標:[ ... ](不含其他括號);用來判斷能否安全去括號
SINGLE_IPA_RE = re.compile(r"^\[[^\[\]]*\]$")
# 動詞三態:gloss 括號(全形或半形)內的 a-b-c
VERBFORMS_RE = re.compile(r"[（(]\s*([A-Za-z]+-[A-Za-z]+-[A-Za-z]+)\s*[)）]")


def strip_md(s: str) -> str:
    """去除 Markdown 粗體標記與行尾換行空白。"""
    s = s.replace("**", "")
    return s.strip()


def fold_accents(s: str) -> str:
    """café → cafe:去掉拉丁字母上的重音(NFKD 後移除組合記號)。"""
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def clean_lookup(word: str) -> str:
    """乾淨查詢字(供抓真人錄音):取斜線前主要拼法、去重音、處理括號、
    僅留字母/連字號/撇號/空白。
    - 括號在開頭(前綴變體,如 '(cock)roach')→ 去括號字元、保留內文 → 'cockroach'
    - 括號在字尾/字中(後綴變體,如 'backward(s)')→ 連內容一併去除 → 'backward'"""
    w = fold_accents(word.strip())
    w = re.split(r"[\/,;]", w)[0].strip()   # 取第一個拼法
    if w.startswith("("):
        w = w.replace("(", "").replace(")", "")
    else:
        w = re.sub(r"\([^)]*\)", "", w)
    w = re.sub(r"[^A-Za-z\-' ]", "", w)
    return w.strip().lower()


def ipa_from_raw(ipa_raw: str) -> str:
    """單一 [..] → 去方括號取內容;多音標(含 (n.)/(v.) 兩式)→ 原樣保留。"""
    if SINGLE_IPA_RE.match(ipa_raw):
        return ipa_raw[1:-1].strip()
    return ipa_raw


def parse_pos(gloss: str):
    """從 gloss 取詞性陣列:掃描所有 'xxx.' 型 token,保留屬於詞性白名單者
    (依出現順序)。支援 'adj./adv.'(無空格)與 'n. ... / v. ...'(有空格)。"""
    pos = []
    for m in POS_TOKEN_RE.finditer(gloss):
        tok = m.group(1)
        if tok.lower() in POS_SET:
            pos.append(tok + ".")
    return pos


def parse_verbforms(gloss: str):
    m = VERBFORMS_RE.search(gloss)
    return m.group(1) if m else None


def parse_md(path, book):
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    words = []
    page_notes = {}
    pages_seen = []
    seq = 0
    page = None
    unit = None
    cur = None          # 目前單字 dict

    def flush_word():
        nonlocal cur
        cur = None

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()

        # 頁標題
        m = re.match(r"^##\s*第\s*(\d+)\s*頁", s)
        if m:
            page = int(m.group(1))
            unit = f"第 {page} 頁"
            if page not in pages_seen:
                pages_seen.append(page)
            cur = None
            i += 1
            continue

        # 頁級筆記
        m = re.match(r"^>\s*📝\s*(.+)$", s)
        if m and page is not None:
            page_notes.setdefault(str(page), []).append(m.group(1).strip())
            i += 1
            continue

        # 單字標題:### word  `[ipa]`
        m = re.match(r"^###\s+(.+?)\s*(?:`([^`]*)`)?\s*$", s)
        if m and page is not None:
            seq += 1
            word = strip_md(m.group(1)).strip()
            ipa_raw = (m.group(2) or "").strip()
            ipa = ipa_from_raw(ipa_raw) if ipa_raw else None
            cur = {
                "id": f"{book}-{seq:04d}",
                "book": book,
                "page": page,
                "unit": unit,
                "word": word,
                "lookup": clean_lookup(word),
                "ipa": ipa or None,
                "ipaRaw": ipa_raw or None,
                "pos": [],
                "gloss": "",
                "verbForms": None,
                "examples": [],
                "notes": [],
                "audioWord": None,
                "imageWord": None,
            }
            words.append(cur)
            i += 1
            continue

        # gloss 行:**...**(單字標題後第一個粗體行)
        if cur is not None and s.startswith("**") and not cur["gloss"]:
            gloss = strip_md(s)
            cur["gloss"] = gloss
            cur["pos"] = parse_pos(gloss)
            cur["verbForms"] = parse_verbforms(gloss)
            i += 1
            continue

        # 單字筆記:- 📝 ...
        m = re.match(r"^-\s*📝\s*(.+)$", s)
        if m and cur is not None:
            cur["notes"].append(strip_md(m.group(1)).strip())
            i += 1
            continue

        # 例句:- 英文(下一行縮排為中譯)
        m = re.match(r"^-\s+(.+)$", line)
        if m and cur is not None and "📝" not in s:
            en = strip_md(m.group(1))
            zh = ""
            # 下一行若非空、非新項目/標題,視為中譯
            if i + 1 < n:
                nxt = lines[i + 1]
                nstrip = nxt.strip()
                if nstrip and not nstrip.startswith(("-", "#", ">", "###")):
                    zh = strip_md(nstrip)
                    i += 1
            cur["examples"].append({"en": en, "zh": zh, "audio": None, "image": None})
            i += 1
            continue

        i += 1

    return words, page_notes, pages_seen


def merge_enrichment(new_words, out_path):
    """把既有檔的音檔/圖片依 id + 內容一致 沿用到新資料上。"""
    if not os.path.exists(out_path):
        return
    try:
        old = json.load(open(out_path, encoding="utf-8"))
        old_by_id = {w["id"]: w for w in old.get("words", [])}
    except Exception:
        return
    for w in new_words:
        o = old_by_id.get(w["id"])
        if not o or o.get("word") != w["word"]:
            continue
        # 單字層加值欄位
        for f in ENRICH_WORD_FIELDS:
            if o.get(f) is not None:
                w[f] = o[f]
        # 例句層:逐句比對 en 一致才沿用 audio/image
        old_ex = {e.get("en"): e for e in o.get("examples", [])}
        for e in w["examples"]:
            oe = old_ex.get(e["en"])
            if oe:
                if oe.get("audio") is not None:
                    e["audio"] = oe["audio"]
                if oe.get("image") is not None:
                    e["image"] = oe["image"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True, help="來源 Markdown 單字本")
    ap.add_argument("--book", required=True, help="book code,如 G1-S1")
    ap.add_argument("--name", default=None, help="顯示名稱,如 高一上 (Level 2)")
    ap.add_argument("--desc", default="", help="描述")
    ap.add_argument("--check", action="store_true", help="只比對既有檔、不寫入")
    args = ap.parse_args()

    md_path = args.md if os.path.isabs(args.md) else os.path.join(ROOT, args.md)
    words, page_notes, pages_seen = parse_md(md_path, args.book)
    example_count = sum(len(w["examples"]) for w in words)
    out_rel = f"data/{args.book}.json"
    out_path = os.path.join(ROOT, out_rel)

    print(f"解析完成:{len(words)} 字、{len(pages_seen)} 頁、{example_count} 例句、"
          f"{len(page_notes)} 頁有筆記")

    if args.check:
        if os.path.exists(out_path):
            old = json.load(open(out_path, encoding="utf-8"))["words"]
            same = len(old) == len(words) and all(
                a["word"] == b["word"] and a["unit"] == b["unit"] and
                [e["en"] for e in a.get("examples", [])] == [e["en"] for e in b["examples"]]
                for a, b in zip(old, words))
            print("與既有檔比對:", "一致 ✓" if same else "不一致 ✗")
        else:
            print("(尚無既有檔可比對)")
        return

    merge_enrichment(words, out_path)
    meta = {
        "book": args.book,
        "name": args.name or args.book,
        "description": args.desc,
        "count": len(words),
        "pages": len(pages_seen),
        "exampleCount": example_count,
        "source": os.path.basename(md_path),
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "pageNotes": page_notes, "words": words},
                  f, ensure_ascii=False, indent=2)
    print(f"已寫入 {out_rel}")

    # 更新 manifest
    manifest = {"books": []}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST, encoding="utf-8"))
    books = manifest.setdefault("books", [])
    row = {"book": args.book, "name": meta["name"], "file": out_rel,
           "count": meta["count"], "pages": meta["pages"], "exampleCount": example_count}
    for i, b in enumerate(books):
        if b["book"] == args.book:
            books[i] = row
            break
    else:
        books.append(row)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"已更新 data/index.json({len(books)} 本)")


if __name__ == "__main__":
    main()
