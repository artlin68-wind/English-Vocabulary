# 背單字 — 高中英文單字記憶 App

給高中生在**通勤、零碎時間用手機背英文單字**的離線網頁 App(PWA)。
每個單字都有**音標、發音、例句、例句中譯**;卡片式瀏覽、可左右滑動、可自動連續朗讀、可離線。
以 **iPhone(iOS Safari 加入主畫面)** 為第一優先,純靜態、無後端、執行期完全離線。

目前內容:**高一上(book code `G1-S1`)共 923 字、34 個單元**。

---

## 功能

- **卡片瀏覽**:正面 單字 / 音標 / 詞性,點卡片翻面看 例句 / 中譯。
- **發音**:點單字播單字、點例句播例句;支援 **0.75x / 1x 語速**。音檔在建置時預先產好、打包進專案,**離線可播**。
- **自動播放(通勤盲聽)**:自動依序念「單字 → 例句」,可設間隔、是否念中譯、單張重複。用單一持久 `<audio>` 串接播放清單並實作 **MediaSession**,**鎖屏 / 控制中心可顯示與操控,螢幕關閉仍能連續朗讀**。
- **單元篩選 / 搜尋 / 進度**:依 Page 單元篩選;搜尋英文或中文;標記「已會 / 待複習」(存 localStorage),可只看待複習 / 未標記。
- **圖片輔助記憶**:單字有代表圖、例句有情境圖(免費授權、乾淨無浮水印);抽象字自動留白、無圖不破版。
- **分單元離線下載**:預設只快取 App 與文字;每個單元一顆「下載」鈕把該單元音檔與圖片存進裝置(Cache Storage),有進度、可一鍵清除釋放空間。
- **大字體 / 單手**:深色高對比、大點擊區(≥44px)、可調字級、避開 Safari 邊緣返回手勢。

---

## 專案結構

```
/                     ← 部署根目錄(GitHub Pages 直接指向這裡)
  index.html          App 進入點(含 iOS PWA meta / apple-touch-icon)
  manifest.json       PWA manifest(display: standalone)
  sw.js               Service Worker(殼與文字 precache;音檔分單元快取)
  css/styles.css
  js/app.js
  icons/              PWA / iOS 圖示(程式產生)
  data/
    index.json        單字本清單 manifest(多本擴充用)
    G1-S1.json        第一本:高一上(923 字,含音標/音檔路徑)
  audio/
    word/G1-S1-XXXX.mp3       單字發音
    sentence/G1-S1-XXXX.mp3   例句發音
  images/
    word/G1-S1-XXXX.jpg       單字輔助圖(Wikipedia,具體字才有)
    sentence/G1-S1-XXXX.jpg   例句情境圖
    credits.json              每張圖的來源/授權/作者(供標註)
  scripts/            建置管線(見下)
  words.json          相容用:即 data/G1-S1.json 的複本(App 實際讀 data/)
  單字.docx           來源檔
```

資料每筆結構:

```json
{
  "id": "G1-S1-0001", "book": "G1-S1", "unit": "Page 5-6",
  "word": "ancient", "lookup": "ancient", "pos": ["adj."],
  "ipa": "/ˈeɪnʃənt/", "ipaSource": "dict",
  "example": "We were impressed by the ruins of an ancient building.",
  "translation": "我們對一處古建築廢墟印象頗深。",
  "audioWord": "audio/word/G1-S1-0001.mp3", "audioWordSource": "tts",
  "audioSentence": "audio/sentence/G1-S1-0001.mp3",
  "imageWord": null, "imageSentence": null
}
```

音標、音檔、圖片路徑都在**建置時**產生並寫入 JSON,執行期不依賴任何外部 API(確保離線)。查不到的欄位給 `null`,App 端優雅降級(不顯示 / 隱藏按鈕)。

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

## 重跑建置管線

所有外部依賴**只在建置時使用**;執行期完全離線。建置腳本皆**斷點續跑**(已產好的跳過)、有進度輸出。

安裝依賴:

```bash
pip install -r scripts/requirements.txt
```

一鍵全跑(docx → 資料 → 音標 → 音檔 → 圖示):

```bash
python scripts/build_all.py --docx 單字.docx --book G1-S1 --name 高一上
```

或分步執行:

```bash
# 1) docx → data/G1-S1.json + 更新 data/index.json
python scripts/build_data.py --docx 單字.docx --book G1-S1 --name 高一上
#    (--check 只比對既有檔、不寫入)

# 2) 補美式音標(eng-to-ipa / CMUdict;查無者標 ipaSource=auto)
python scripts/gen_ipa.py --book G1-S1

# 3) 產音檔(單字 + 例句)
python scripts/gen_audio.py --book G1-S1
#    預設全部用 edge-tts 神經語音(穩定、100% 覆蓋、音質自然、iOS 保證支援的 mp3)
#    --human 則單字優先抓 Wikimedia Commons 真人母語錄音(En-us / Lingua Libre),
#            用內附 ffmpeg 轉 mp3,查無者退回 TTS,並以 audioWordSource 標 human/tts。

# 4) 產單字 / 例句圖片(Phase 2;Wikipedia 免費授權,乾淨無浮水印)
python scripts/gen_images.py --book G1-S1
#    預設只用 Wikipedia(en.wikipedia pageimages,一次查 50 標題、快又穩),
#    具體名詞有圖、抽象字留白。例句圖用句中關鍵名詞查。
#    --openverse 可額外用 Openverse(限博物館/Wikimedia 乾淨來源)補更多圖。

# 5) 產 PWA / iOS 圖示
python scripts/gen_icons.py
```

一鍵含圖片:`python scripts/build_all.py --docx 單字.docx --book G1-S1 --name 高一上 --images`

`build_data.py` 具**冪等**性:若 `data/<book>.json` 已存在,會依 id 保留既有的音標 / 音檔 / 圖片欄位,只更新文字並補新字,重跑不會清掉已產好的資產。

### 發音來源說明

- **例句**:一律用 **edge-tts**(微軟 Neural 語音,免費、**不需 API KEY**、音質自然接近真人)。
- **單字**:預設同樣用 edge-tts(神經語音,非機械電子音)。加 `--human` 可優先抓真人母語錄音;每筆以 `audioWordSource` 記錄 `human` / `tts`,方便日後把 TTS 版換成真人版而不動 App。
- 音檔格式:mono **mp3**(iOS Safari 保證支援;不用 Opus/OGG)。全書約 **31 MB**。
- **KEY 安全**:本專案預設引擎皆免 KEY。若改用需 KEY 的引擎(Azure/Google/OpenAI/ElevenLabs 等),KEY **只在建置腳本於本機用**,從環境變數讀取、加入 `.gitignore`,**嚴禁寫進前端 / JSON / 版控**;產完只把 `.mp3` 打包進 App。

### 新增一本單字書(不用改 App)

1. 準備一份**同格式** docx(表格 4 欄:單字 / 詞性 / 例句 / 中譯,段落用 Page 標題分單元)。
2. 跑 `build_all.py --docx 新書.docx --book G1-S2 --name 高一下`。
   → 產出 `data/G1-S2.json`、音檔 `audio/*/G1-S2-*.mp3`,並在 `data/index.json` 加一列。
3. App 從 manifest 動態載入,重新整理即多一本;既有本的 ID 不變、進度/音檔不受影響。

---

## 部署(GitHub Pages,免費 HTTPS)

PWA 需 **HTTPS**(`file://` 或純區網 http 無法安裝)。建議 GitHub Pages:

1. 把整個專案根目錄推到 GitHub repo。
2. repo → **Settings → Pages** → Source 選 `main` 分支、根目錄 `/`。
3. 幾分鐘後得到 `https://<你的帳號>.github.io/<repo>/` 網址,手機開啟即可安裝。

> 音檔約 31 MB、圖片約 40 MB(合計約 70 MB),建議用 Git LFS 或確認 repo 容量;若不想入庫,也可只推程式與資料,音檔/圖片另外託管到同源路徑。

### iOS 安裝與使用

1. iPhone **Safari** 開上述網址。
2. 底部**分享鈕 → 「加入主畫面」**。
3. **從主畫面開啟**(這一步很重要):已加入主畫面的 PWA 不受 iOS「未安裝網站約 7 天清快取」限制,離線音檔才會可靠保留。
4. 進「設定 → 離線下載」逐單元下載音檔;之後開飛航模式仍可瀏覽並播放,鎖屏可連續朗讀。

> 個人使用用 PWA 即可,**不需 Apple 開發者帳號、不需上架 App Store**。若日後想包成原生 App 上架,才需要 Mac + Xcode + 每年 US$99 帳號(可用 Capacitor 包裝),屬額外選項。

---

## 資料來源與授權

- 單字 / 例句 / 中譯:隨附 `單字.docx`(高一上)。
- 音標:[eng-to-ipa](https://pypi.org/project/eng-to-ipa/)(以 CMUdict 為底,General American)。
- 單字真人錄音(`--human` 時):[Wikimedia Commons](https://commons.wikimedia.org/)(Wiktionary `En-us-*`、Lingua Libre `LL-Q1860 (eng)-*`),多為 CC 授權;請於實際散布前確認個別檔案授權。
- 神經語音:[edge-tts](https://github.com/rany2/edge-tts)(微軟 Neural 線上合成,建置時使用)。
- 音檔轉檔:[imageio-ffmpeg](https://pypi.org/project/imageio-ffmpeg/) 內附 ffmpeg。

請於實際對外散布時,再次確認各來源授權允許此教育用途。

---

## 已知限制 / 後續

- 目前單字發音為神經語音(TTS)。要真人版可跑 `gen_audio.py --human`(覆蓋率視網路而定,查無者仍為 TTS)。
- **Phase 2(已做)**:單字 / 例句圖片,來源為 **Wikipedia / Wikimedia Commons**(CC/公有領域,乾淨無浮水印)。具體名詞多有圖,**抽象字(如 avoid、honest)自動留白**,App 有圖才顯示、無圖不破版。覆蓋率約一半;想補更多可跑 `gen_images.py --openverse`。圖片授權明細見 `images/credits.json`,對外散布前請確認個別檔案授權。
- 3 個單字(postcard / principle / waitress)來源檔無例句(標「—」),故無例句音檔/圖片,App 顯示「此字無例句」。
- **Phase 3(未做)**:自我測驗與間隔複習(spaced repetition)、進度統計優化。
