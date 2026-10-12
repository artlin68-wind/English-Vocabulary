#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_all.py — 一鍵重跑整條建置管線(全部斷點續跑,已產好的會跳過)。

v2:單字來源為 Markdown 單字本(已含音標/gloss/多例句/三態/筆記),
   故不再跑 gen_ipa(音標已內含於資料)。

依序執行:
  1) build_data.py  md → data/<book>.json + 更新 index.json(--md 指定來源)
  2) gen_audio.py   產單字/逐例句音檔(預設 TTS;--human 則單字優先真人錄音)
  3) gen_images.py  產單字/逐例句圖片(Wikipedia 免費授權;--openverse 補更多)
  4) gen_icons.py   產 PWA / iOS 圖示

用法:
  python scripts/build_all.py --md Level2_單字本_p1-72.md --book G1-S1 --name "高一上 (Level 2)"
  python scripts/build_all.py --md Level2_單字本_p1-72.md --book G1-S1 --human --images
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(script, *args):
    cmd = [PY, os.path.join(HERE, script), *args]
    print(f"\n=== 執行 {script} {' '.join(args)} ===", flush=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        sys.exit(f"{script} 失敗(exit {r.returncode})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True, help="來源 Markdown 單字本(v2)")
    ap.add_argument("--book", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--human", action="store_true", help="單字優先抓真人錄音")
    ap.add_argument("--images", action="store_true", help="產圖片(Phase 2)")
    ap.add_argument("--openverse", action="store_true", help="圖片額外用 Openverse 補圖")
    args = ap.parse_args()

    run("build_data.py", "--md", args.md, "--book", args.book,
        *(["--name", args.name] if args.name else []))
    audio_args = ["--book", args.book]
    if args.human:
        audio_args.append("--human")
    run("gen_audio.py", *audio_args)
    if args.images:
        img_args = ["--book", args.book]
        if args.openverse:
            img_args.append("--openverse")
        run("gen_images.py", *img_args)
    run("gen_icons.py")
    print("\n✓ 全部完成。可用 `python -m http.server` 於專案根目錄本地預覽。")


if __name__ == "__main__":
    main()
