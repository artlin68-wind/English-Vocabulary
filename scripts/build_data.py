#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_data.py — Phase 0:把單字 docx 轉成 data/<book>.json 並更新 data/index.json。

docx 結構:每個「Page 區塊」= 一段標題(如「Page 5–6 (Level 2)」)+ 一個 4 欄表格
          (單字 / 詞性 / 例句 / 中譯)。以文件實際先後順序把標題配對到其後的表格。

產出每筆:id(book 前綴、各本獨立四位數流水號)、book、unit、word、lookup、
         pos[]、example、translation,以及 ipa/audio/image 等欄位(此腳本一律留 null)。

可擴充:任何同格式 docx 都能 build 成新的一本;新增一本只在 index.json 加一列,
       既有本的 ID 不重編。

安全(冪等):若目標 json 已存在,會以 id 保留既有的 ipa / 音檔 / 圖片等「加值欄位」,
             只更新文字內容並補上新字——重跑整條管線不會清掉已產好的音標/音檔。

用法:
  python scripts/build_data.py --docx 單字.docx --book G1-S1 --name 高一上
  python scripts/build_data.py --docx 單字.docx --book G1-S1 --name 高一上 --check   # 只比對不寫檔
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

try:
    import docx  # python-docx
    from docx.oxml.ns import qn
except ImportError:
    sys.exit("缺少 python-docx,請先執行:pip install python-docx")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "index.json")

# 這些是「加值欄位」,重建時從既有檔沿用(以 id 對應),避免清掉音標/音檔/圖片
ENRICH_FIELDS = ["ipa", "ipaSource", "audioWord", "audioWordSource",
                 "audioSentence", "imageWord", "imageSentence"]


def clean_lookup(word: str) -> str:
    """乾淨查詢字:去括號變體、取斜線前主要拼法。lookup 保留原字母(含重音)。"""
    w = word.strip()
    w = re.split(r"[\/,;]", w)[0]
    w = re.sub(r"\([^)]*\)", "", w)
    w = re.sub(r"\s+", " ", w)
    return w.strip().lower()


def norm_unit(heading: str) -> str:
    """『Page 5–6 (Level 2)』→『Page 5-6』;抓不到就用整段標題。"""
    m = re.search(r"Page\s*([0-9]+)\s*[–\-~]\s*([0-9]+)", heading)
    if m:
        return f"Page {m.group(1)}-{m.group(2)}"
    return heading.strip() or "Unit"


def split_pos(cell: str):
    parts = re.split(r"[\/,、;&]|\s{2,}", cell.strip())
    return [p.strip() for p in parts if p.strip()]


def iter_blocks(document):
    """依文件實際順序產出 ('p', text) / ('tbl', table)。"""
    body = document.element.body
    tbl_iter = iter(document.tables)
    para_by_elem = {p._p: p for p in document.paragraphs}
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            p = para_by_elem.get(child)
            if p is not None:
                yield ("p", p.text)
        elif child.tag == qn("w:tbl"):
            yield ("tbl", next(tbl_iter))


def parse_docx(path, book):
    document = docx.Document(path)
    blocks = list(iter_blocks(document))

    # 本 docx 的版面是「表格在前、Page 標題緊接在後」;故每個表格的單元名
    # 取其後方第一個非空段落。找不到就沿用前一個標題。
    def heading_after(idx):
        for j in range(idx + 1, len(blocks)):
            k, v = blocks[j]
            if k == "p" and v.strip():
                return v.strip()
            if k == "tbl":
                break
        return None

    words = []
    seq = 0
    last_end = None      # 上一個單元的結束頁碼
    units_order = []
    for i, (kind, val) in enumerate(blocks):
        if kind == "p":
            continue
        # 表格 → 決定單元名
        h = heading_after(i)
        m = re.search(r"Page\s*([0-9]+)\s*[–\-~]\s*([0-9]+)", h or "")
        if m:
            unit = f"Page {m.group(1)}-{m.group(2)}"
            last_end = int(m.group(2))
        elif last_end is not None:
            # docx 缺此表格的 Page 標題(如最後一塊):沿頁碼 +2 推定下一組
            unit = f"Page {last_end + 1}-{last_end + 2}"
            last_end += 2
        else:
            unit = norm_unit(h or "Unit")
        if unit not in units_order:
            units_order.append(unit)
        rows = val.rows
        for r in rows:
            cells = [c.text.strip() for c in r.cells]
            if len(cells) < 4:
                continue
            word = cells[0]
            # 跳過表頭 / 空列
            if not word or word.startswith("單字") or "(Word)" in word:
                continue
            seq += 1
            words.append({
                "id": f"{book}-{seq:04d}",
                "book": book,
                "unit": unit,
                "word": word,
                "lookup": clean_lookup(word),
                "pos": split_pos(cells[1]),
                "example": cells[2],
                "translation": cells[3],
                "ipa": None,
                "audioWord": None,
                "audioWordSource": None,
                "audioSentence": None,
                "imageWord": None,
                "imageSentence": None,
            })
    return words, units_order


def merge_enrichment(new_words, out_path):
    """把既有檔的加值欄位(音標/音檔/圖片)依 id 沿用到新資料上。"""
    if not os.path.exists(out_path):
        return
    try:
        old = json.load(open(out_path, encoding="utf-8"))
        old_by_id = {w["id"]: w for w in old.get("words", [])}
    except Exception:
        return
    for w in new_words:
        o = old_by_id.get(w["id"])
        if not o:
            continue
        # 只有在「文字內容一致」時才沿用音檔,避免內容變了還配到舊音檔
        if o.get("word") == w["word"] and o.get("example") == w["example"]:
            for f in ENRICH_FIELDS:
                if o.get(f) is not None:
                    w[f] = o[f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True, help="來源 docx 路徑")
    ap.add_argument("--book", required=True, help="book code,如 G1-S1")
    ap.add_argument("--name", default=None, help="顯示名稱,如 高一上")
    ap.add_argument("--desc", default="", help="描述")
    ap.add_argument("--check", action="store_true", help="只比對既有檔、不寫入")
    args = ap.parse_args()

    docx_path = args.docx if os.path.isabs(args.docx) else os.path.join(ROOT, args.docx)
    words, units_order = parse_docx(docx_path, args.book)
    out_rel = f"data/{args.book}.json"
    out_path = os.path.join(ROOT, out_rel)

    print(f"解析完成:{len(words)} 字、{len(units_order)} 單元")

    if args.check:
        if os.path.exists(out_path):
            old = json.load(open(out_path, encoding="utf-8"))["words"]
            same = len(old) == len(words) and all(
                a["word"] == b["word"] and a["unit"] == b["unit"] and
                a["example"] == b["example"]
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
        "units": len(units_order),
        "source": os.path.basename(docx_path),
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "words": words}, f, ensure_ascii=False, indent=2)
    print(f"已寫入 {out_rel}")

    # 更新 manifest
    manifest = {"books": []}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST, encoding="utf-8"))
    books = manifest.setdefault("books", [])
    row = {"book": args.book, "name": meta["name"], "file": out_rel,
           "count": meta["count"], "units": meta["units"]}
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
