# 文件庫左欄改 3 tab（全部／未分類／資料夾）

文件庫左欄目前把「全部／未分類／各資料夾」攤成一列，新增鈕固定在欄頭。使用者要求左欄頂端改成 3 個可切換的 tab：只有選到「資料夾」才出現新增鈕與資料夾清單，「全部／未分類」時左欄底下空白；UI/UX 要好看，狀態用 localStorage 記住。

## 決策

### F1. 左欄頂端 3 tab，狀態持久化

- 左欄頂端 3 個 tab：全部／未分類／資料夾，可切換。
- 全部／未分類 tab：tab 之下左欄空白，右側表格顯示全部／未分類文件。
- 資料夾 tab：tab 之下才出現新增資料夾鈕（plus icon，inline 建立表單照舊）與資料夾清單。
- 目前 tab 持久化到 localStorage（走 `src/utils/storage.ts`，versioned key）；預設「全部」。

### F2. 資料夾 item 滿欄寬、無邊框；選定資料夾也持久化

- 資料夾 item 吃滿左欄寬度、沒有邊框：拿掉既有的 2px 左邊線與圓角底色，active 狀態只靠字重與顏色表達。
- 列上改名（edit icon）與刪除（trash icon，確認走 ConfirmDialog，L5 不變；刪除後文件變未分類）維持 hover 顯示。
- 點資料夾讓右側表格顯示該資料夾內容；選定的資料夾 id 也持久化到 localStorage。持久化的資料夾已不存在時退回未選定；資料夾 tab 未選定時表格顯示全部文件。

### F3. 拖曳保留，開始拖曳自動切到資料夾 tab

- 文件列仍可拖曳；開始拖曳時左欄自動切到「資料夾」tab，讓 drop 目標出現（全部／未分類 tab 沒有資料夾列，沒有 drop 目標）。
- 未分類仍是 drop 目標（拖上去＝取消分類），位置在「未分類」tab 本身，拖曳中高亮。
- 列選單「移至資料夾」modal 維持當備援；拖曳不得是唯一移動路徑。

## 理由

- 使用者直接指定版面：左欄頂端 3 tab、新增鈕與資料夾只在資料夾 tab、全部／未分類底下空白、狀態進 localStorage。
- 3 tab 把「看文件」（全部／未分類）與「管理資料夾」（資料夾）分開，左欄不再一長列。
- 文件庫是常回訪頁；記住 tab 與選定資料夾讓下次進來直接回到上次的檢視。

## 影響

- `docs/frontend.md` 文件區段與頁面清單更新；AppTabs 註記「文件頁已不再使用」改為文件庫左欄使用。
- 實作：`DocumentFolderSidebar` 重構成 tab 版（或換名）、`DocumentListView` 的 `folderFilter` 拆成「左欄 tab」與「選定資料夾」兩個狀態並持久化；`components/documents/folders.ts` 的拖曳 payload 不變。