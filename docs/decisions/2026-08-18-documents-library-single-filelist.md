# 文件庫左欄收回單一 filelist（推翻 F1 的 3 tab）

3 tab 版（`2026-08-18-documents-library-sidebar-tabs.md` F1–F3）上線後，使用者發現邏輯不順：全部／未分類 tab 下沒有資料夾列，拖文件分類時得先切到資料夾 tab 才有 drop 目標，主要動線（拖曳分類）被中斷。使用者決定把「全部／未分類」放回資料夾底下的 filelist：點擊顯示全部或未分類，清單同時兼做檢視切換與資料夾管理。

## 決策

### G1. 左欄收回單一清單（推翻 F1）

- 拿掉 3 tab；左欄是單一清單：全部／未分類／各資料夾。
- 選定項目持久化到 localStorage（單一 key，`quiz-forge:documents-left-filelist:v1`），預設「全部」；F1 的兩個舊 key 不再讀取，殘留值無須處理。
- 全部／未分類項目與資料夾項目同一視覺：滿欄寬、無邊框、active 只靠字重與顏色、純文字計數。

### G2. 新增資料夾 band 常駐

- 欄頂的新增資料夾 band（plus icon 置中、整行可點、行下分隔線）常駐顯示，不再綁定 tab。

### G3. 拖曳維持，拿掉自動切 tab

- drop 目標常駐可見：未分類項目（drop＝取消分類）與各資料夾項目；全部不是 drop 目標。
- F3 的「開始拖曳自動切到資料夾 tab」隨 tab 一併拿掉。
- 列選單「移至資料夾」modal 維持當備援；拖曳不得是唯一移動路徑。

## 理由

- 使用者直接拍板：「把全部、未分類歸類在資料夾底下的 filelist 比較合理，點擊後顯示全部或未分類，這樣才可以進行資料夾分類。」
- 3 tab 版把「看文件」與「管理資料夾」分開，代價是拖曳分類必须先切 tab；單一清單讓 drop 目標永遠在畫面上。
- F2 的視覺決定（無邊框 item、選定持久化）與新增 band 的樣式都保留，只收回 tab 結構。

## 影響

- `docs/frontend.md` 文件區左欄段落改寫；AppTabs 註記與頁面清單同步。
- 實作：`DocumentLibrarySidebar` 拿掉 tab 列、加回全部／未分類項目；`DocumentListView` 狀態收回單一持久化 filter、拿掉 dragstart 自動切 tab。
- `2026-08-18-documents-library-sidebar-tabs.md` 的 F1 被本文件推翻；F2／F3 的視覺與備援部分隨 G1–G3 調整後保留。