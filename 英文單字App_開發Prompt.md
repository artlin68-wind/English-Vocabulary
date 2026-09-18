# 開發需求 Prompt — 高中英文單字記憶 App

> 用途:把這整份內容(從下方「== PROMPT 開始 ==」到結尾)複製貼給 Claude Code 或其他 coding agent,讓它據此實作。
> 這份規格已對照過來源檔 `單字.docx` 的實際結構撰寫。

---

== PROMPT 開始 ==

你是一位資深前端 / PWA 工程師。請依以下規格,從零實作一個給**高中生在通勤搭車、零碎時間用手機背英文單字**的離線網頁 App。請主動做技術決策、把它做到可實際使用,不要只給片段。

## 1. 產品目標
- 使用情境:高中生在搭車、排隊等**短暫零碎時間**,單手拿手機背單字。
- **目標平台:iPhone(iOS Safari 的 PWA,安裝到主畫面)。** 一切技術選擇以 iOS Safari 相容為第一優先(詳見 §7A、§8)。
- 核心價值:每個單字都有**音標、發音、例句、例句中譯**;之後再加**圖片**輔助記憶。
- 硬性體驗要求:
  - 字體**不可太小**(內文最小 18px,單字主體 ≥ 32px,可讓使用者再放大)。
  - 單字與例句**都要能點擊發音**。
  - 發音**要接近真人、不能是機械電子音**(做法見 §5)。
  - **可離線使用**(地鐵、隧道無訊號也能背),要能從 iOS Safari「加入主畫面」當 App 用(PWA)。
  - 單手操作:大點擊區、可用滑動切換上一個/下一個單字。

## 2. 資料來源
- 來源檔:`單字.docx`(共 923 個單字,高中一年級上學期,字母序 ancient→windy)。
- 結構:檔內有 34 個表格,每個表格對應一個「Page 區塊」(段落標題形如 `Page 5–6 (Level 2)`),可作為**單元(unit)**分組。
- 每個表格為 4 欄,表頭為:
  | 單字 (Word) | 詞性 (POS) | 例句 (Example Sentence) | 中譯 (Translation) |
- 範例列:
  - `ancient | adj. | We were impressed by the ruins of an ancient building. | 我們對一處古建築廢墟印象頗深。`
  - `avoid | v. | I avoided him as much as possible. | 我盡可能避開他。`
- 注意:部分單字含變體標記,如 `backward(s)`;詞性可能有多個。解析時保留原字串,另存一個「乾淨查詢用」欄位(去掉括號/斜線,取主要拼法)供音標與發音查找。

## 2A. 可擴充性 — 未來要能持續加入更多單字(必做,先設計好)
這批 923 字只是**第一本(高一上,book code `G1-S1`)**。設計時必須讓日後「再丟一份同格式的新單字檔進來、跑一次建置就多一本」,**不用改 App 程式**:
- **多單字本結構:** 每一本自成一個資料檔(如 `data/G1-S1.json`、`data/G1-S2.json`…),外加一個 **manifest `data/index.json`** 列出所有單字本(book code、顯示名稱、單元數、字數、檔案路徑)。App 從 manifest 動態載入,新增一本只需在 manifest 加一列。
- **穩定 ID:** 單字 ID 以 **book code 為前綴**(如 `G1-S1-0001`),各本獨立編號;新增一本**不得重編既有本的 ID**,以免既有進度/音檔/圖片對應跑掉。
- **資產以 ID 定址:** 音檔/圖片路徑一律用 `audio/word/{id}.mp3`、`audio/sentence/{id}.mp3` 這種以 ID 命名的規則,新增單字只是多幾個檔,不動既有。
- **建置管線可增量:** 腳本接受任意同格式 docx,產出對應 `data/<book>.json` 並更新 manifest;已存在的音標/音檔/圖片**跳過不重產**(斷點續跑)。
- **App 端:** 提供「選擇單字本 / 級別」的入口,再進單元篩選;進度、已下載離線資料都以 book + unit 為單位分別管理。
- **相容備註:** 隨附的 `words.json` 即第一本內容,建置時請視為 `G1-S1`(可直接改名 `data/G1-S1.json` 並補上 book 欄位與 ID 前綴),並建立 `data/index.json`。

## 3. 建置流程與資料管線(Phase 0,先做)
寫一支 build-time 腳本(Python 或 Node 皆可),把 `單字.docx` 轉成 `words.json`,每筆結構:
```json
{
  "id": "G1-S1-0001",
  "book": "G1-S1",
  "unit": "Page 5-6",
  "word": "ancient",
  "lookup": "ancient",
  "pos": ["adj."],
  "ipa": "/ˈeɪnʃənt/",
  "example": "We were impressed by the ruins of an ancient building.",
  "translation": "我們對一處古建築廢墟印象頗深。",
  "audioWord": "audio/word/0001.mp3",
  "audioSentence": "audio/sentence/0001.mp3",
  "imageWord": null,
  "imageSentence": null
}
```
- 音標、音檔、圖片路徑都在**建置時**產生並寫入 JSON,執行期不再依賴外部 API(確保離線)。
- 若某欄產不出來(如查無音標),欄位給 null,App 端需優雅降級。

## 4. 音標 (IPA)
- 建置時離線產生,優先用開源字典資料集對照(如 `ipa-dict` 的 en_US 對照表,或 CMUdict 轉 IPA);查不到的字用 `espeak-ng` 的音素輸出補上並標記為「自動推定」。
- 以美式音標為主。存進 `words.json` 的 `ipa` 欄。

## 5. 發音音檔(關鍵:要接近真人)
**單字發音**
- 建置時優先抓**真人母語錄音**:用免費字典來源(如 Free Dictionary API `dictionaryapi.dev`,其回傳的 audio 連到 Wiktionary/Commons 的真人錄音 mp3)下載成本地檔。
- 查無真人錄音的字,退回用**高品質神經語音**合成(見下),並在資料裡標記來源,方便日後補真人版。

**例句發音**
- 用**高品質神經網路 TTS** 建置時預先合成成音檔。推薦 `edge-tts`(微軟 Neural 語音,免費、可腳本化,音質自然接近真人,如 `en-US-AriaNeural`、`en-US-GuyNeural`);或 `Piper` 作為完全離線的替代。**不要用瀏覽器內建 SpeechSynthesis 當主方案**(音質不穩、常是機械音)。

**API KEY 與安全性(重要)**
- `edge-tts` **不需要 API KEY**,優先採用。
- 若改用需要 KEY 的引擎(Azure / Google / OpenAI TTS / ElevenLabs 等,音質更接近真人):KEY **只在建置腳本、於本機用來預先產生音檔**,產完只把 `.mp3` 打包進 App。
- **嚴禁把任何 API KEY 寫進前端 / PWA / `words.json` / 版控**(會被公開盜用,且違反離線原則)。KEY 從環境變數讀取,並加入 `.gitignore`。
- 釐清:用不用 KEY 與「是否真人發音」無關——真人發音來自字典真人錄音(單字),TTS(不論免費或付費、有無 KEY)皆為神經語音合成(例句)。

**共同要求**
- 所有音檔在建置時**預先產好、打包進專案**,執行期直接播本地檔 →可離線(執行期不需要任何 KEY)。
- 格式:mono、**mp3 或 AAC(.m4a)**、語音用 32–48 kbps 即可(單字約 10–20KB、例句約 40–80KB)。**不要用 Opus / OGG——iOS Safari `<audio>` 對其支援不一致。** 統一用 iOS 保證支援的 mp3 或 AAC。
- 全部音檔預估約 50–80MB;用 Service Worker 於安裝時 precache(或首次開啟時背景快取),確保離線可播。iOS 儲存配額有限,見 §8 的分單元下載策略。
- App 端播放:點單字播單字、點例句播例句;提供「重複播放」與「0.75x / 1x 語速」切換。
- **iOS 背景 / 鎖屏播放(「放口袋盲聽」關鍵):** 用**單一持久的 `<audio>` 元素**串接播放清單(監聽 `ended` 事件接續下一段),並實作 **MediaSession API**(`navigator.mediaSession` metadata 與 play/pause/next/prev handlers),讓鎖屏 / 控制中心能顯示與操控,螢幕關閉仍能連續朗讀。iOS 需**使用者先點一下**才能啟動音訊(autoplay 限制),自動播放模式須由一個明確的「開始」手勢啟動。

## 6. 圖片(Phase 2,先把 §1–§5 做完再做)
- 每個單字一張輔助記憶插圖、每個例句一張情境插圖。
- 建置時產生(AI 生成插圖,風格統一;或退而求其次用免費圖庫/icon)。抽象單字找不到貼切圖時允許留白。
- 圖片路徑寫入 `words.json` 的 `imageWord` / `imageSentence`,App 端有圖才顯示、無圖不破版。

## 7. App 功能與 UI/UX
**技術棧建議**:React + Vite + TypeScript,搭 `vite-plugin-pwa`(Workbox)處理離線快取與安裝;純靜態部署即可。(若你判斷用 vanilla JS 更輕更穩也可,但務必達成離線 PWA。)

**畫面與模式**
- 卡片式(flashcard)瀏覽:一次一個單字,顯示 單字 / 音標 / 詞性,點一下翻面看 例句 / 中譯。
- 左右滑動切換上一個/下一個;大型上一個/下一個按鈕(單手可按)。
- 依 Page 單元篩選;單字搜尋。
- 進度追蹤:標記「已會 / 待複習」,存 localStorage 或 IndexedDB;可只看待複習。
- **自動播放模式(通勤重點)**:免手動,自動依序念「單字 → 例句」,可設間隔與是否念中譯,可放口袋盲聽。
- (Phase 3)簡單自我測驗與間隔複習(spaced repetition)。

**視覺**
- 預設深色主題、高對比;字體大、行距寬。
- 大點擊區(≥ 44px);播放/翻面/切換都要好按。
- RWD 以手機直式為主(iPhone 直式優先)。

## 7A. iOS / iPhone 專屬需求(必做)
- **HTML head 需含 iOS PWA meta 標籤:**
  - `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`(配合瀏海/動態島用 `env(safe-area-inset-*)` 留安全區)
  - `<meta name="apple-mobile-web-app-capable" content="yes">`
  - `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">`
  - `<meta name="apple-mobile-web-app-title" content="背單字">`
  - `<link rel="apple-touch-icon" href="...180x180.png">`(iOS 主畫面圖示;manifest 的 icon iOS 不完全採用,務必另外提供 apple-touch-icon)
- **手勢:** 用 iOS 慣性的左右滑動切換;避免與 Safari 邊緣返回手勢衝突(滑動區域避開最左/最右邊緣)。
- **音訊解鎖:** 首次使用者點擊時解鎖 `<audio>`(播一段極短無聲或直接 play),之後才能程式化連續播放;自動播放模式一定要由明確手勢啟動(見 §5)。
- **字級:** 在 `<input>` 等避免 < 16px 以防 iOS 自動放大;提供 App 內字級調整(rem 縮放)。
- **測試:** 以實機 iPhone Safari 驗收「加入主畫面 → 從主畫面開啟 → 開飛航模式 → 仍可瀏覽並播放已快取音檔 → 鎖屏仍能自動連續朗讀」。

## 8. 離線 / PWA(iOS 重點)
- 完整 `manifest.json`(`display: standalone`)+ Service Worker;從 **iOS Safari** 用「分享 → 加入主畫面」安裝。
- **必須以 HTTPS 部署**(Service Worker 的前提;`file://` 或純區網 http 無法安裝 PWA)。建議 **GitHub Pages**(免費、HTTPS,手機開啟即可安裝)。
- **iOS 快取存續:** iOS 對「未安裝」的網站約 7 天未用即清除快取;**已加入主畫面(standalone)的 PWA 不受此 7 天清除限制**,所以務必引導使用者「加入主畫面」後從主畫面開啟,離線音檔才會可靠保留。
- **iOS 儲存配額有限**(音檔 50–80MB 可能觸頂):
  - 提供**分單元下載**:預設只快取 App 殼與 `words.json`,音檔改為「下載此單元」按鈕逐單元快取,有進度顯示。
  - 用 Cache Storage 存音檔;超額時給明確提示,並可讓使用者刪除已下載單元釋放空間。
- 首次載入後,已下載單元的 `words.json`、音檔、(Phase 2 的)圖片皆離線可存取。
- **部署與更新替代方案(說明給使用者):** 個人使用用 PWA 即可,不需要 Apple 開發者帳號、不需上架 App Store。若日後真的想上架原生 App,才需要 Mac + Xcode + 每年 US$99 開發者帳號(可用 Capacitor 包裝),屬額外選項、非本專案必要。

## 9. 專案結構(建議)
```
/scripts        # docx→json、抓/合成音檔、產音標、(Phase2)產圖 的建置腳本
/public/audio   # word/*.mp3, sentence/*.mp3
/public/images  # (Phase2)
/src            # App 原始碼
/public/words.json
```
- README 寫清楚:如何重跑建置管線、如何本地預覽、如何部署(建議 GitHub Pages,方便手機開啟並安裝為 PWA)。

## 10. 建議實作順序(里程碑)
1. **Phase 0**:`單字.docx` → `words.json`(先不含音標/音檔,跑通 923 筆解析與單元分組)。
2. **Phase 1**:補音標 + 單字/例句音檔 + 核心 App(卡片瀏覽、發音、大字體、單元篩選、自動播放、離線 PWA)。← 先交付可用版本。
3. **Phase 2**:加圖片。
4. **Phase 3**:測驗、間隔複習、進度統計優化。

## 11. 驗收標準(Definition of Done)
- [ ] `words.json` 正確含 923 筆,單元分組與四欄內容與來源檔一致(抽查 10 筆比對)。
- [ ] 每筆有音標(自動推定者有標記)。
- [ ] 每個單字、每個例句都能點擊播放,音質自然、非機械電子音。
- [ ] 手機直式下字體夠大、單手可操作、可左右滑動切換。
- [ ] 開飛航模式仍可瀏覽單字並播放已快取音檔。
- [ ] 可加入主畫面當 App 開啟。
- [ ] 自動播放模式可連續朗讀單字與例句。
- [ ] README 讓人能重跑建置管線並部署。

## 12. 注意事項
- 使用的字典/語音/圖片來源請確認授權允許此用途,並在 README 標註來源。
- 923 字 × (單字+例句) 音檔量大,建置腳本要能**斷點續跑**(已產生的跳過)、有進度輸出、對外部來源做重試與速率控制。
- 所有外部依賴只在**建置時**使用;執行期必須全離線可用。

== PROMPT 結束 ==
