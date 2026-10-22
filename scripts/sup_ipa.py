#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sup_ipa.py — 為補充本 kind=word 的單字填 KK 音標(ipa / ipaRaw),與主本排版一致。

來源優先序:
  1) 主本 data/G1-S1.json 有同字 → 直接沿用其 ipaRaw(風格完全一致)
  2) 否則用下方人工校對的 KK 表(主本慣例:͵ 次重音、ɚ/ɝ、ḷ/ṇ、字尾 y→ɪ、aʊ)
用法:python scripts/sup_ipa.py
"""
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KK = {
    "accidentally": "͵æksəˈdɛntḷɪ", "afterward": "ˈæftɚwɚd", "amaze": "əˈmez",
    "astonish": "əˈstɑnɪʃ", "awake": "əˈwek", "breathe": "brið",
    "communicate": "kəˈmjunə͵ket", "connect": "kəˈnɛkt", "creature": "ˈkritʃɚ",
    "depress": "dɪˈprɛs", "disappoint": "͵dɪsəˈpɔɪnt", "embarrass": "ɪmˈbærəs",
    "embrace": "ɪmˈbres", "float": "flot", "forever": "fɚˈɛvɚ",
    "fortunate": "ˈfɔrtʃənɪt", "grab": "græb", "greeting": "ˈgritɪŋ",
    "impress": "ɪmˈprɛs", "inspire": "ɪnˈspaɪr", "journey": "ˈdʒɝnɪ",
    "memorize": "ˈmɛmə͵raɪz", "nap": "næp", "personally": "ˈpɝsṇḷɪ",
    "present": "prɪˈzɛnt", "recall": "rɪˈkɔl", "reflect": "rɪˈflɛkt",
    "refresh": "rɪˈfrɛʃ", "remind": "rɪˈmaɪnd", "romance": "roˈmæns",
    "ruin": "ˈruɪn", "sacred": "ˈsekrɪd", "skip": "skɪp", "vary": "ˈvɛrɪ",
    "yell": "jɛl",
    # 單字補充 Unit 4–6
    "ability": "əˈbɪlətɪ", "accomplish": "əˈkɑmplɪʃ", "alert": "əˈlɝt",
    "assign": "əˈsaɪn", "attraction": "əˈtrækʃən", "behavior": "bɪˈhevjɚ",
    "celebration": "͵sɛləˈbreʃən", "consume": "kənˈsjum", "convenience": "kənˈvinjəns",
    "crowded": "ˈkraʊdɪd", "detect": "dɪˈtɛkt", "drift": "drɪft",
    "eagerly": "ˈigɚlɪ", "envy": "ˈɛnvɪ", "expose": "ɪkˈspoz",
    "firmly": "ˈfɝmlɪ", "globe": "glob", "harm": "hɑrm",
    "infected": "ɪnˈfɛktɪd", "item": "ˈaɪtəm", "keen": "kin",
    "landmark": "ˈlænd͵mɑrk", "locate": "loˈket", "monument": "ˈmɑnjəmənt",
    "obviously": "ˈɑbvɪəslɪ", "perform": "pɚˈfɔrm", "plastic": "ˈplæstɪk",
    "poisonous": "ˈpɔɪzṇəs", "predict": "prɪˈdɪkt", "product": "ˈprɑdəkt",
    "properly": "ˈprɑpɚlɪ", "recycling": "riˈsaɪklɪŋ", "represent": "͵rɛprɪˈzɛnt",
    "reward": "rɪˈwɔrd", "slavery": "ˈslevərɪ", "specific": "spɪˈsɪfɪk",
    "statue": "ˈstætʃu", "substance": "ˈsʌbstəns", "surround": "səˈraʊnd",
    "symbolize": "ˈsɪmbḷ͵aɪz", "tourist": "ˈtʊrɪst", "treatment": "ˈtritmənt",
    "unfair": "ʌnˈfɛr",
}

def main():
    main_words = json.load(open(os.path.join(ROOT, "data/G1-S1.json"), encoding="utf-8"))["words"]
    ref = {}
    for w in main_words:
        ref.setdefault((w.get("lookup") or w["word"]).lower(), w)
    p = os.path.join(ROOT, "data/G1-S1-SUP.json")
    data = json.load(open(p, encoding="utf-8"))
    n_main = n_kk = 0
    missing = []
    for w in data["words"]:
        key = w["word"].lower()
        if key in ref and ref[key].get("ipaRaw"):
            w["ipa"], w["ipaRaw"], w["ipaSource"] = ref[key]["ipa"], ref[key]["ipaRaw"], "main"
            n_main += 1
        elif key in KK:
            w["ipa"], w["ipaRaw"], w["ipaSource"] = KK[key], f"[{KK[key]}]", "kk"
            n_kk += 1
        else:
            missing.append(w["word"])
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"沿用主本 {n_main} / KK 表 {n_kk} / 缺 {len(missing)} {missing}")

if __name__ == "__main__":
    main()
