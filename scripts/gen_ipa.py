#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_ipa.py — 建置時離線產生美式音標 (IPA)。

來源:eng-to-ipa (以 CMUdict 為底,General American)。
- 查得到:ipa 填 `/.../`,ipaSource = "dict"。
- 查不到:標記 ipaSource = "auto"(目前無 espeak-ng,保留 null 供日後補),
  App 端須對 null 優雅降級。

特性:斷點續跑(已有 ipa 的字預設跳過,--force 可重產)、進度輸出。
可處理 manifest (data/index.json) 內任一本;預設全部處理。

用法:
  python scripts/gen_ipa.py                 # 處理 manifest 內所有書
  python scripts/gen_ipa.py --book G1-S1    # 只處理指定書
  python scripts/gen_ipa.py --force         # 重產所有(忽略既有 ipa)
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "index.json")

try:
    import eng_to_ipa as e2i
except ImportError:
    sys.exit("缺少 eng-to-ipa,請先執行:pip install eng-to-ipa")


def clean_lookup(word: str) -> str:
    """取乾淨查詢字:去括號變體、取斜線前主要拼法、去非字母字元。
    e.g. 'backward(s)' -> 'backward','take/took' -> 'take'"""
    w = word.strip()
    w = re.split(r"[\/,;]", w)[0]          # 取第一個拼法
    w = re.sub(r"\([^)]*\)", "", w)         # 去掉 (s) 這類變體
    w = re.sub(r"[^A-Za-z\-' ]", "", w)     # 只留字母/連字號/撇號/空白
    return w.strip().lower()


# 人工補正:eng-to-ipa/CMUdict 查無的字(含重音、複合字)。視為 dict 品質。
OVERRIDES = {
    "cafe": "/kæˈfeɪ/",
    "café": "/kæˈfeɪ/",
    "stomachache": "/ˈstʌmək.eɪk/",
    "toothache": "/ˈtuθ.eɪk/",
}


def to_ipa(lookup: str):
    """回傳 (ipa_or_None, source)。source: 'dict' 或 'auto'。"""
    if not lookup:
        return None, "auto"
    if lookup in OVERRIDES:
        return OVERRIDES[lookup], "dict"
    raw = e2i.convert(lookup)
    # eng-to-ipa 查不到時,回傳原字並在字尾加 '*'(可能多字時個別加)
    if "*" in raw:
        return None, "auto"
    ipa = raw.strip()
    if not ipa:
        return None, "auto"
    return f"/{ipa}/", "dict"


def process_book(path: str, force: bool):
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as f:
        data = json.load(f)
    words = data["words"]
    total = len(words)
    done = 0
    filled = 0
    auto = 0
    for w in words:
        # lookup 欄若缺,現算一個
        if not w.get("lookup"):
            w["lookup"] = clean_lookup(w["word"])
        if w.get("ipa") and not force:
            done += 1
            continue
        ipa, source = to_ipa(w["lookup"])
        w["ipa"] = ipa
        w["ipaSource"] = source
        if ipa:
            filled += 1
        else:
            auto += 1
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{total} ...", flush=True)
    with open(full, encoding="utf-8", mode="w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[{data['meta']['book']}] 共 {total} 字|新填 IPA {filled}|查無(auto/null) {auto}")
    # 列出查無的字,方便人工補
    misses = [w["word"] for w in words if not w.get("ipa")]
    if misses:
        print("  查無音標:", ", ".join(misses))
    return total, filled, auto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", help="只處理指定 book code")
    ap.add_argument("--force", action="store_true", help="忽略既有 ipa 重產")
    args = ap.parse_args()

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    books = manifest["books"]
    if args.book:
        books = [b for b in books if b["book"] == args.book]
        if not books:
            sys.exit(f"manifest 內找不到 book: {args.book}")

    for b in books:
        print(f"== 處理 {b['book']} ({b['file']}) ==")
        process_book(b["file"], args.force)


if __name__ == "__main__":
    main()
