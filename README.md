# 背單字 — 高中英文單字記憶 App

給高中生在**通勤、零碎時間用手機背英文單字**的離線網頁 App(PWA)。
每個單字都有**音標、發音、(多個)例句與例句中譯、多詞性解釋、動詞三態、📝 筆記**;卡片式瀏覽、可左右滑動、可自動連續朗讀、可離線。
以 **iPhone(iOS Safari 加入主畫面)** 為第一優先,純靜態、無後端、執行期完全離線。

目前內容:
- **高一上 Level 2(`G1-S1`)**:1003 字、72 頁、1169 例句(主本)。
- **高一上 補充(`G1-S1-SUP`)**:68 個詞類變化字(含衍生詞)+ 53 個 Unit 4–6 單字(含搭配詞)+ 35 條片語(Lesson 1–4)。此本卡片結構不同(`kind: word / phrase`),App 依 `kind` 自動切換呈現。

> 多單字本:`data/index.json` 列出所有本(含 `type: vocab | supplement`),App 從選單切換;新增一本只加一列、不改 App。

---

## 功能

- **卡片瀏覽**:正面 單字 / 音標(`ipaRaw`)/ 詞性,點卡片翻面看 多詞性解釋(`gloss`)/ **逐句例句** / 動詞三態 / 📝 筆記。
- **發音**:點單字播單字、點**任一例句**播該句;支援 **0.75x / 1x 語速**。音檔在建置時預先產好、打包進專案,**離線可播**。
- **自動播放(通勤盲聽)**:自動依序念「單字 → 各例句」,可設間隔、是否念中譯、單張重複。用單一持久 `<audio>` 串接播放清單並實作 **MediaSession**,**鎖屏 / 控制中心可顯示與操控,螢幕關閉仍能連續朗讀**。
- **頁篩選 / 搜尋 / 進度**:依「第 N 頁」篩選(第 1–72 頁);搜尋英文 / 解釋 / 例句;標記「已會 / 待複習」(存 localStorage),可只看待複習 / 未標記。
- **頁級補充**:進入某頁時顯示該頁 `pageNotes`(📝)。
- **圖片輔助記憶(Phase 2)**:單字有代表圖、例句有情境圖(免費授權、乾淨無浮水印);抽象字自動留白、無圖不破版。
- **分頁離線下載**:預設只快取 App 與文字;每頁一顆「下載」鈕把該頁音檔與圖片存進裝置(Cache Storage),有進度、可一鍵清除釋放空間。
- **大字體 / 單手**:深色高對比、大點擊區(≥44px)、可調字級、避開 Safari 邊緣返回手勢。

---

## 專案結構

```
/                     ← 部署根目錄(GitHub Pages 直接指向這裡)
  index.html          App 進入點(含 iOS PWA meta / apple-touch-icon)
  manifest.json       PWA manifest(display: standalone)
  sw.js               Service Worker(殼與文字 precache;音檔分頁快取)
  css/styles.css
  js/app.js
  icons/              PWA / iOS 圖示(程式產生)
  data/
    index.json        單字本清單 manifest(多本擴充用)
    G1-S1.json        第一本:高一上 Level 2(1003 字,含音標/多例句/音檔路徑)
  audio/
    word/{id}.mp3            單字發音
    sentence/{id}-{n}.mp3    例句發音(n = 該字第幾句例句,1-based)
  images/
    word/{id}.jpg           單字輔助圖(Wikipedia,具體字才有)
    sentence/{id}-{n}.jpg   例句情境圖
    credits.json            每張圖的來源/授權/作者(供標註)
  scripts/            建置管線(見下)
    voices/           Piper 離線語音模型(.onnx + .onnx.json,不入庫亦可)
  words.json          相容用:即 data/G1-S1.json 的複本(App 實際讀 data/)
  Level2_單字本_p1-72.md   單字來源檔(編輯它即可改內容,見下)
```

資料每筆結構(v2 schema):

```json
{
  "id": "G1-S1-0005", "book": "G1-S1", "page": 1, "unit": "第 1 頁",
  "word": "account", "lookup": "account",
  "ipa": "əˈkaunt", "ipaRaw": "[əˈkaunt]",
  "pos": ["n.", "v."],
  "gloss": "n. 帳戶；帳目(複數)；描述 / v. 解釋",
  "verbForms": null,
  "examples": [
    { "en": "There were only 500 dollars in his bank account.",
      "zh": "他戶頭裡只有 500 元。",
      "audio": "audio/sentence/G1-S1-0005-1.mp3", "image": null }
  ],
  "notes": [],
  "audioWord": "audio/word/G1-S1-0005.mp3", "audioWordSource": "piper",
  "imageWord": null
}
```

檔案頂層另含 `meta` 與 `pageNotes`(頁級 📝 補充,key 為頁碼字串)。
音標已內含於資料;音檔 / 圖片路徑在**建置時**產生並寫入 JSON,執行期不依賴任何外部 API(確保離線)。查不到的欄位給 `null`,App 端優雅降級(不顯示 / 隱藏按鈕)。

---

## 本地預覽

需要用 **HTTP 伺服器**開啟(Service Worker 不能在 `file://` 下運作):

```bash
# 在專案根目錄
python -m http.server 8137
# 瀏覽器開 http://127.0.0.1:8137/index.html
```

手機直式檢視最佳。桌機可用方向鍵 ←/→ 切換、空白鍵翻面、Enter 播單字(方便測試)。

---

## 更新單字內容

單字來源是 **`Level2_單字本_p1-72.md`**(純文字,好編輯)。格式:

```markdown
## 第 1 頁
> 📝 present 出席                 ← 該頁的頁級筆記(可多行)

### absence  `[ˈæbsns]`           ← 單字 + 音標(反引號內含方括號)
**n. 缺席**                        ← 解釋(多詞性用 / 分段;動詞三態寫在括號內)

- She never speaks ill of anyone in their **absence**.   ← 例句(英文)
  她從不趁人不在時說別人的壞話。                             ← 下一行縮排為中譯
- 📝 be + absent                   ← 該單字的筆記
```

改完 md 後,重建 `data/G1-S1.json`:

```bash
python scripts/build_data.py --md Level2_單字本_p1-72.md --book G1-S1 --name "高一上 (Level 2)"
#   (--check 只比對既有檔、不寫入)
```

`build_data.py` 具**冪等**性:若 `data/G1-S1.json` 已存在,會依 id + 內容一致 保留既有的音檔 / 圖片路徑(`audioWord` / `examples[i].audio` / `imageWord` / `examples[i].image`),只更新文字並補新字 —— 重跑不會清掉已產好的資產。**新增/修改內容後,只需對「新字或改過的句子」重跑音檔步驟**(已存在者自動跳過)。

---

## 重跑建置管線

所有外部依賴**只在建置時使用**;執行期完全離線。建置腳本皆**斷點續跑**(已產好的跳過)、有進度輸出。

安裝依賴:

```bash
pip install -r scripts/requirements.txt
```

一鍵全跑(md → 資料 → 音檔 → 圖示):

```bash
python scripts/build_all.py --md Level2_單字本_p1-72.md --book G1-S1 --name "高一上 (Level 2)"
```

或分步執行:

```bash
# 1) md → data/G1-S1.json + 更新 data/index.json
python scripts/build_data.py --md Level2_單字本_p1-72.md --book G1-S1 --name "高一上 (Level 2)"

# 2) 產音檔(單字 + 逐例句)——見下方「發音引擎」
python scripts/gen_audio.py --book G1-S1 --piper        # 離線 Piper(推薦)
#   或 python scripts/gen_audio.py --book G1-S1          # edge-tts(需網路,端點偶有限制)

# 3) 產單字 / 逐例句圖片(Phase 2;Wikipedia 免費授權,乾淨無浮水印)
python scripts/gen_images.py --book G1-S1
#   具體名詞有圖、抽象字留白;例句圖用句中關鍵名詞查。
#   --openverse 可額外用 Openverse(限博物館/Wikimedia 乾淨來源)補更多圖。

# 4) 產 PWA / iOS 圖示
python scripts/gen_icons.py
```

> 音標**已內含於來源 md**,故 v2 不再需要「自動產生 IPA」步驟(舊 `gen_ipa.py` 已停用)。

### 發音引擎(要接近真人、非機械電子音)

兩種引擎,都免 API KEY、產出 mono **mp3**(iOS Safari 保證支援,不用 Opus/OGG):

- **Piper(`--piper`,推薦):完全離線**神經語音,不需網路、不受任何雲端端點限制。
  需先下載語音模型到 `scripts/voices/`:
  ```bash
  python -m piper.download_voices en_US-lessac-medium --data-dir scripts/voices
  # 若該下載因憑證/網路失敗,可直接抓兩個檔到 scripts/voices/:
  #   en_US-lessac-medium.onnx 與 en_US-lessac-medium.onnx.json
  #   (來源:huggingface.co/rhasspy/piper-voices …/en/en_US/lessac/medium/)
  ```
  可用 `--piper-model` 指定其他 `.onnx`。單字音以 `audioWordSource=piper` 標記。
- **edge-tts(預設):** 微軟 Neural 線上合成,音質自然但**需要連到微軟端點**(某些網路 / 系統時間不符時會回 403)。單字加 `--human` 可優先抓 Wikimedia Commons 真人母語錄音,查無退回 TTS,以 `audioWordSource` 記 `human`/`tts`。

> **KEY 安全**:本專案預設引擎皆免 KEY。若改用需 KEY 的引擎(Azure/Google/OpenAI/ElevenLabs 等),KEY **只在建置腳本於本機用**,從環境變數讀取、加入 `.gitignore`,**嚴禁寫進前端 / JSON / 版控**;產完只把 `.mp3` 打包進 App。

### 新增一本單字書(不用改 App)

1. 準備一份**同格式**的 md 單字本(見上「更新單字內容」)。
2. 跑 `build_all.py --md 新書.md --book G1-S2 --name 高一下 --piper`。
   → 產出 `data/G1-S2.json`、音檔 `audio/*/G1-S2-*.mp3`,並在 `data/index.json` 加一列。
3. App 從 manifest 動態載入,重新整理即多一本;既有本的 ID 不變、進度/音檔不受影響。

---

## 部署(GitHub Pages,免費 HTTPS)

PWA 需 **HTTPS**(`file://` 或純區網 http 無法安裝)。建議 GitHub Pages:

1. 把整個專案根目錄推到 GitHub repo。
2. repo → **Settings → Pages** → Source 選 `main` 分支、根目錄 `/`。
3. 幾分鐘後得到 `https://<你的帳號>.github.io/<repo>/` 網址,手機開啟即可安裝。

> 音檔約 60–90 MB、圖片另計,建議確認 repo 容量或用 Git LFS;若不想入庫,也可只推程式與資料,音檔/圖片另外託管到同源路徑。`scripts/voices/` 的 Piper 模型(約 60 MB)只在建置時需要,可不入庫。

### iOS 安裝與使用

1. iPhone **Safari** 開上述網址。
2. 底部**分享鈕 → 「加入主畫面」**。
3. **從主畫面開啟**(這一步很重要):已加入主畫面的 PWA 不受 iOS「未安裝網站約 7 天清快取」限制,離線音檔才會可靠保留。
4. 進「設定 → 離線下載」逐頁下載音檔;之後開飛航模式仍可瀏覽並播放,鎖屏可連續朗讀。

> 個人使用用 PWA 即可,**不需 Apple 開發者帳號、不需上架 App Store**。若日後想包成原生 App 上架,才需要 Mac + Xcode + 每年 US$99 帳號(可用 Capacitor 包裝),屬額外選項。

---

## 資料來源與授權

- 單字 / 音標 / 例句 / 中譯 / 筆記:隨附 `Level2_單字本_p1-72.md`(高中英文 Level 2)。
- 離線神經語音:[Piper](https://github.com/OHF-Voice/piper1-gpl) + [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices)(語音模型多為寬鬆授權,散布前請確認個別模型授權)。
- 線上神經語音(`edge-tts` 時):[edge-tts](https://github.com/rany2/edge-tts)(微軟 Neural 線上合成,建置時使用)。
- 單字真人錄音(`--human` 時):[Wikimedia Commons](https://commons.wikimedia.org/)(Wiktionary `En-us-*`、Lingua Libre `LL-Q1860 (eng)-*`),多為 CC 授權。
- 圖片(Phase 2):[Wikipedia / Wikimedia Commons](https://commons.wikimedia.org/)(CC / 公有領域);明細見 `images/credits.json`。
- 音檔轉檔:[imageio-ffmpeg](https://pypi.org/project/imageio-ffmpeg/) 內附 ffmpeg。

請於實際對外散布時,再次確認各來源授權允許此教育用途。

---

## 已知限制 / 後續

- 單字發音預設為神經語音(Piper 離線 / 或 edge-tts)。要真人版可跑 `gen_audio.py --human`(覆蓋率視網路而定,查無者仍為 TTS)。
- **Phase 2(圖片)**:來源為 Wikipedia / Wikimedia Commons(CC/公有領域,乾淨無浮水印)。具體名詞多有圖,**抽象字自動留白**,App 有圖才顯示、無圖不破版。覆蓋率約一半;想補更多可跑 `gen_images.py --openverse`。
- 原單字本有 1 個重複字(`chalk` 於第 10、11 頁各一次),依來源**保留兩筆**。
- **Phase 3(未做)**:自我測驗與間隔複習(spaced repetition)、進度統計優化。
```
