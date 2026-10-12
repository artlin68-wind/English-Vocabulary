# 開發需求 Prompt v2 — 高中英文單字記憶 App（含資料結構更新）

> 用途:把從下方「== PROMPT 開始 ==」到結尾整段複製貼給 Claude Code。
> 本版為 **v2 更新版**:單字來源改為更完整的 `Level2_單字本_p1-72.md`(1003 字、已含音標、多例句、筆記、動詞三態)。**若你已依 v1(923 字、docx 來源)寫過程式,本次請依 §0 做資料結構與 UI 的 coding 更新,不是重寫。**

---

== PROMPT 開始 ==

你是一位資深前端 / PWA 工程師。目標是一個給**高中生在 iPhone 上、通勤零碎時間背英文單字**的離線網頁 App(iOS Safari PWA)。**本次是版本更新**:單字資料從舊版(923 字、docx)換成新版(1003 字、含音標與多例句的單字本)。請依 §0 先讀變更重點,再據全文實作/更新。

## 0. 本次更新重點(CODING 更新指示)
相對於舊版,資料變更如下,**App 程式與建置管線都要跟著改**:
1. **字數 923 → 1003**,來源改為 `Level2_單字本_p1-72.md`。
2. **音標已內含於資料**(每個字都有 `ipa`)→ **移除「自動產生 IPA」的建置步驟**,App 直接顯示即可。
3. **每個單字可有「多個例句」**(共 1169 句),資料結構由「單一例句欄位」改為 **`examples` 陣列**;UI 要能顯示並逐句發音。
4. 新增欄位:`gloss`(含多詞性中文解釋)、`pos`(詞性陣列)、`verbForms`(動詞三態,如 `beat-beat-beaten`)、`notes`(單字層 📝 筆記)、`pageNotes`(頁級 📝 補充)。UI 要呈現這些。
5. **分組單位改為「頁」**(第 1–72 頁,共 72 頁),取代舊版的 Page 區塊。單元篩選改用頁。
6. **音檔改為逐例句產生**:`examples[i].audio`(例句)+ `audioWord`(單字);圖片同理 `examples[i].image` + `imageWord`。
7. **資料已解析完成並隨附**(見 §2、§3),Claude Code **不需再解析原始 md/pdf**,直接用 `data/*.json`;只需補音檔/圖片欄位。
8. **新增一本「補充版」`G1-S1-SUP`**(詞類變化 68 字 + 片語 20 條),已隨附 `data/G1-S1-SUP.json`,並登錄於 `data/index.json`。此本卡片結構與主本不同,見 §2B。App 要支援此第二種內容類型。
> 若從零開始,忽略「更新」字樣,直接依全文實作即可。

## 1. 產品目標
- 使用情境:高中生搭車、排隊等**短暫零碎時間**,單手拿 iPhone 背單字。
- **目標平台:iPhone(iOS Safari 的 PWA,安裝到主畫面)。** 一切技術選擇以 iOS Safari 相容為第一優先(§7A、§8)。
- 核心價值:每個單字有**音標、發音、(多個)例句與例句中譯、📝 筆記**;之後再加**圖片**輔助記憶。
- 硬性體驗要求:
  - 字體**不可太小**(內文最小 18px,單字主體 ≥ 32px,可讓使用者再放大)。
  - 單字與**每一個例句**都要能點擊發音。
  - 發音**要接近真人、不能是機械電子音**(做法見 §5)。
  - **可離線使用**,可從 iOS Safari「加入主畫面」當 App 用(PWA)。
  - 單手操作:大點擊區、可左右滑動切換上一個/下一個單字。

## 2. 資料來源與結構
- 來源:`Level2_單字本_p1-72.md`(高中英文 Level 2,p.1–72,共 **1003 字、1169 例句**)。
- **已解析完成的資料隨附於 `data/G1-S1.json`(與 `words.json` 同內容),Claude Code 直接使用。** 另附 `data/index.json`(單字本 manifest,見 §2A)。
- 單字資料 schema(每筆):
```json
{
  "id": "G1-S1-0005",
  "book": "G1-S1",
  "page": 1,
  "unit": "第 1 頁",
  "word": "account",
  "lookup": "account",          // 乾淨查詢用(去括號/斜線/重音),供抓真人錄音
  "ipa": "əˈkaunt",             // 已內含,直接顯示
  "ipaRaw": "[əˈkaunt]",        // 原始帶括號字串(少數字含 (n.)/(v.) 兩式)
  "pos": ["n.", "v."],
  "gloss": "n. 帳戶；帳目(複數)；描述 / v. 解釋",
  "verbForms": null,             // 動詞三態字串,如 "beat-beat-beaten";無則 null
  "examples": [
    { "en": "There were only 500 dollars in his bank account.",
      "zh": "他戶頭裡只有 500 元。", "audio": null, "image": null }
    /* ...可有多句... */
  ],
  "notes": [],                   // 單字層 📝 筆記(字串陣列)
  "audioWord": null,             // 單字發音檔路徑(建置時填)
  "imageWord": null              // 單字圖片路徑(Phase 2 填)
}
```
- 檔案頂層另含 `meta` 與 `pageNotes`(頁級 📝 補充,key 為頁碼字串):
```json
{ "meta": { "book":"G1-S1","name":"高一上 (Level 2)","count":1003,"pages":72,"exampleCount":1169 },
  "pageNotes": { "1": ["present 出席"], "2": ["foreign affairs 外交部","have an affair with 緋聞"] },
  "words": [ /* 1003 筆 */ ] }
```
- 已知:僅 1 個重複字(`chalk` 於第 10、11 頁各一次)——原單字本如此,**保留兩筆**即可。

## 2A. 可擴充性 — 未來要能持續加入更多單字(必做)
這本是**第一本(book code `G1-S1`)**。設計要讓日後「再加一本同格式單字本、跑一次建置就多一本」,不用改 App:
- **多單字本結構:** 每本一個 `data/<book>.json`,外加 manifest `data/index.json` 列出所有本(book、名稱、字數、頁數、檔案路徑)。App 從 manifest 動態載入,新增一本只在 manifest 加一列。
- **穩定 ID:** 以 book code 為前綴(`G1-S1-0001`);新增一本**不得重編既有本 ID**。
- **資產以 ID 定址:** 音檔/圖片用 `audio/word/{id}.mp3`、`audio/sentence/{id}-{例句序號}.mp3`,新增只是多檔。
- **建置可增量:** 已存在的音檔/圖片**跳過不重產**(斷點續跑)。
- **App 端:** 提供「選擇單字本」入口,再進頁篩選;進度、離線下載以 book + 頁為單位管理。

## 2B. 補充版單字本（`G1-S1-SUP`，已隨附）
補充版與主本結構不同,是獨立一本(透過 §2A 的 manifest 掛入),含**兩種內容(`kind`)**,各自有單元:
- `kind: "word"`(詞類變化,68 字,單元「詞類變化補充」):
```json
{ "id":"G1-S1-SUP-W003","book":"G1-S1-SUP","kind":"word","unit":"詞類變化補充",
  "word":"amaze","pos":"動詞","meaning":"使人驚奇",
  "derivatives":[ {"form":"amazing","detail":"形容詞: 令人大感驚奇的"},
                  {"form":"amazement","detail":"名詞: 驚奇"} ],
  "ipa":null,"audioWord":null,"imageWord":null }
```
- `kind: "phrase"`(片語,20 條,單元依 Lesson:「片語 Lesson 1：Firsts in Life」等):
```json
{ "id":"G1-S1-SUP-P001","book":"G1-S1-SUP","kind":"phrase","lesson":1,
  "lessonTitle":"Firsts in Life","unit":"片語 Lesson 1：Firsts in Life",
  "phrase":"the rest (of)","meaning":"其餘（的……）",
  "definition":"the remaining part of something or the others in a group",
  "example":"Daryl took a few bites of the cake and then gave the rest of it to his little sister.",
  "exampleZh":null,"audioPhrase":null,"audioExample":null }
```
- 檔案頂層:`meta`(wordCount 68 / phraseCount 20)、`units`(4 個單元字串陣列)、`words`、`phrases` 兩陣列。
- **此本無音標、無例句中譯。** `exampleZh` 預留 null,可日後補中譯(要的話建置時用翻譯 API,一樣只在建置時)。
- 發音:`word` 的單字、各 `derivatives[].form`、`phrase` 本身、`phrase` 的 `example` 都可做發音檔(真人錄音優先用於單字/衍生字;片語與例句用 §5 的神經語音)。
- App 要支援選到此本時以對應卡片呈現(見 §7 補充版卡片)。

## 3. 建置管線
- **md → json 已完成**(隨附 `data/G1-S1.json`),Claude Code 不需重做解析。若日後要重跑,管線需還原本版欄位(ipa/gloss/pos/verbForms/examples[]/notes/pageNotes)。
- 仍需建置產出:**音檔(§5)**、(Phase 2)**圖片(§6)**,把路徑寫回對應欄位(`audioWord`、`examples[i].audio`、`imageWord`、`examples[i].image`)。
- 所有外部來源只在**建置時**使用;執行期全離線。

## 4. 音標
- **已內含於資料(`ipa` / `ipaRaw`),不需再產生。** App 直接顯示;以 `ipaRaw` 呈現(含括號)或用 `ipa` 自行加 `/ /`。少數字 `ipaRaw` 內含 `(n.)`/`(v.)` 兩式,原樣顯示即可。

## 5. 發音音檔(關鍵:要接近真人)
**單字發音(`audioWord`)**
- 建置時優先抓**真人母語錄音**(免費字典來源,如 Free Dictionary API `dictionaryapi.dev`,其 audio 連 Wiktionary/Commons 真人 mp3),以 `lookup` 查詢;查無者退回高品質神經語音,並標記來源。

**例句發音(`examples[i].audio`,逐句)**
- 用**高品質神經 TTS** 預先合成。推薦 `edge-tts`(微軟 Neural,免費、免 KEY、自然,如 `en-US-AriaNeural`/`en-US-GuyNeural`);或 `Piper`(完全離線)。**不要用瀏覽器內建 SpeechSynthesis 當主方案**(機械音)。

**API KEY 與安全性(重要)**
- `edge-tts` **不需 API KEY**,優先採用。
- 若改用需 KEY 的引擎(Azure/Google/OpenAI TTS/ElevenLabs,更像真人):KEY **只在建置腳本於本機用**,產完只把 mp3 打包進 App。
- **嚴禁把任何 KEY 寫進前端 / PWA / json / 版控**;KEY 從環境變數讀取並加入 `.gitignore`。
- 釐清:用不用 KEY 與「是否真人」無關——真人=字典真人錄音(單字);TTS(不論免費付費)皆為神經語音合成(例句)。

**共同要求**
- 音檔建置時**預先產好、打包**,執行期直接播本地檔(不需任何 KEY)→可離線。
- 格式:mono、**mp3 或 AAC(.m4a)**、32–48 kbps。**不要 Opus / OGG**(iOS Safari 支援不一致)。
- 預估音檔量:單字 1003 + 例句 1169 ≈ 2172 檔、約 60–90MB;用 Service Worker 快取,配額策略見 §8。
- App 端:點單字播單字、**點任一例句播該句**;提供「重複播放」與「0.75x / 1x 語速」。
- **iOS 背景/鎖屏播放(「放口袋盲聽」關鍵):** 用**單一持久 `<audio>`** 串接播放清單(聽 `ended` 接下一段),並實作 **MediaSession API**(metadata + play/pause/next/prev handlers),鎖屏/控制中心可顯示操控。iOS 需**使用者先點一下**才能啟動音訊,自動播放須由明確「開始」手勢啟動。

## 6. 圖片(Phase 2,先把 §1–§5、§7 做完再做)
- 每個單字一張輔助記憶插圖(`imageWord`);每個例句一張情境插圖(`examples[i].image`)。
- 建置時產生(AI 生成插圖,風格統一;或免費圖庫/icon)。抽象字找不到貼切圖允許留白。
- App 端有圖才顯示、無圖不破版。

## 7. App 功能與 UI/UX
**技術棧建議**:React + Vite + TypeScript + `vite-plugin-pwa`(Workbox)做離線快取與安裝;純靜態部署。(若判斷 vanilla JS 更穩亦可,但務必達成離線 PWA。)

**單字卡內容(依新 schema 呈現)**
- 正面:`word`(大字)、`ipaRaw` 音標、`pos` 詞性、單字發音鈕。
- 背面/展開:`gloss`(多詞性中文解釋)、**`examples` 逐句**(英文 + 中譯 + 各自發音鈕)、`verbForms`(有才顯示,標成動詞三態)、`notes`(📝 單字筆記)。
- 頁級補充:進入某頁時顯示該頁 `pageNotes`(📝)。

**補充版卡片(`G1-S1-SUP`,§2B)**
- `kind:"word"`:顯示 `word`(大字)+ 單字發音鈕、`pos`、`meaning`,並列出 `derivatives`(每項 `form` + `detail`,`form` 可點擊發音)。無音標/例句。
- `kind:"phrase"`:顯示 `phrase`(大字)+ 發音鈕、`meaning`(中文)、`definition`(英文定義)、`example`(例句,可發音);`exampleZh` 有才顯示。
- 補充版以「單字本選擇 → 單元(詞類變化補充 / 片語 Lesson 1–3)」進入,與主本並列。

**畫面與模式**
- 卡片式瀏覽:一次一字,點擊翻面/展開看解釋與例句。
- 左右滑動切換上一/下一字;大型上一/下一按鈕(單手可按)。
- **依「頁」篩選(第 1–72 頁)**;單字搜尋(比對 word / 中文)。
- 進度追蹤:標記「已會 / 待複習」,存 localStorage 或 IndexedDB;可只看待複習。
- **自動播放模式(通勤重點)**:自動依序念「單字 → 各例句」,可設間隔與是否念中譯,可放口袋盲聽(見 §5 iOS 作法)。
- (Phase 3)自我測驗與間隔複習(spaced repetition)。

**視覺**
- 預設深色主題、高對比;字體大、行距寬;iPhone 直式優先。
- 大點擊區(≥ 44px);播放/翻面/切換好按。

## 7A. iOS / iPhone 專屬需求(必做)
- head 需含 iOS PWA meta:
  - `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`(配合瀏海用 `env(safe-area-inset-*)`)
  - `<meta name="apple-mobile-web-app-capable" content="yes">`
  - `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">`
  - `<meta name="apple-mobile-web-app-title" content="背單字">`
  - `<link rel="apple-touch-icon" href="...180x180.png">`(iOS 不完全採用 manifest icon,務必另附 apple-touch-icon)
- 手勢:左右滑動切換;避開 Safari 最左/右邊緣返回手勢。
- 音訊解鎖:首次點擊時解鎖 `<audio>`,之後才能程式化連續播放。
- 字級:`<input>` 避免 < 16px(防 iOS 自動放大);提供 App 內字級調整(rem)。
- 驗收用實機 iPhone Safari:加入主畫面 → 從主畫面開啟 → 飛航模式仍可瀏覽並播放已快取音檔 → 鎖屏仍能自動連續朗讀。

## 8. 離線 / PWA(iOS 重點)
- 完整 `manifest.json`(`display: standalone`)+ Service Worker;從 **iOS Safari「分享 → 加入主畫面」** 安裝。
- **必須 HTTPS 部署**(Service Worker 前提;`file://`、純區網 http 無法裝 PWA)。建議 **GitHub Pages**(免費、HTTPS,手機開啟即可裝)。
- **iOS 快取存續:** 未安裝的網站約 7 天未用即清;**已加入主畫面的 PWA 不受此限**——務必引導使用者加主畫面後從主畫面開啟,離線音檔才留得住。
- **iOS 儲存配額有限**(音檔 60–90MB 可能觸頂):
  - 預設只快取 App 殼與 `data/*.json`;音檔改為**「下載此頁 / 此單字本」**逐段快取,有進度顯示。
  - 用 Cache Storage 存音檔;超額給提示,並可刪除已下載內容釋放空間。
- 已下載部分的 json、音檔、(Phase 2)圖片皆離線可存取。
- **部署替代方案(說明給使用者):** 個人用 PWA 即可,不需 Apple 開發者帳號、不用上架;要上架原生 App 才需 Mac+Xcode+年費 US$99(可用 Capacitor 包裝),屬額外選項。

## 9. 專案結構(建議)
```
/scripts         # 抓真人錄音、合成例句 TTS、(Phase2)產圖 的建置腳本(可增量)
/public/data     # index.json, G1-S1.json(隨附)
/public/audio    # word/{id}.mp3, sentence/{id}-{n}.mp3
/public/images   # (Phase2) word/{id}.jpg, sentence/{id}-{n}.jpg
/src             # App 原始碼
```
- README:如何補音檔/圖片、本地預覽、部署 GitHub Pages、如何加新單字本。

## 10. 建議實作順序(里程碑)
1. **Phase 1**:載入 `data/G1-S1.json` → 核心 App(卡片、音標顯示、多例句、📝/三態呈現、頁篩選、搜尋、字級、深色)+ 單字/逐句發音 + 自動播放 + 離線 PWA。← 先交付可用版本。
2. **Phase 2**:加圖片(`imageWord` / `examples[].image`)。
3. **Phase 3**:測驗、間隔複習、進度統計。

## 11. 驗收標準(Definition of Done)
- [ ] 載入 **1003 筆**、**72 頁**、**1169 例句**,內容與 `data/G1-S1.json` 一致(抽查 10 筆)。
- [ ] 每筆顯示音標;多詞性 `gloss`、動詞三態、📝 筆記、頁級補充都有呈現。
- [ ] 單字與**每個例句**都能點擊播放,音質自然、非機械電子音。
- [ ] iPhone 直式字體夠大、單手可操作、可左右滑動切換。
- [ ] 加入主畫面後、開飛航模式仍可瀏覽並播放已快取音檔;鎖屏可自動連續朗讀。
- [ ] 以 HTTPS(GitHub Pages)部署,iOS Safari 可加入主畫面。
- [ ] 補充版 `G1-S1-SUP` 可正常載入:68 詞類變化字(含衍生詞)+ 20 片語(依 Lesson 1–3 分單元),卡片依 `kind` 正確呈現。
- [ ] 新增一本單字本只需加 `data/<book>.json` 並在 `data/index.json` 加一列,不改 App 程式。
- [ ] README 可讓人補音檔/圖片並部署。

## 12. 注意事項
- 字典/語音/圖片來源確認授權允許此用途,README 標註。
- 音檔量大(約 2172 檔),建置腳本要**斷點續跑**(已產生跳過)、有進度、對外部來源重試與速率控制。
- 外部依賴只在建置時用;執行期全離線、不需任何 KEY。

== PROMPT 結束 ==
