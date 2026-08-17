# 文件庫資料夾刪除改 icon，確認改走 ConfirmDialog

使用者在 `/documents` 資料夾列上標出「刪除」文字鈕佔列，要求改成 icon；按下後仍要跳出確認。本決策只處理這個例外，不改動文件刪除或批次丟棄的文案規則。

## 決策

### L5. 資料夾列刪除改 trash icon，確認改走既有 ConfirmDialog

- 資料夾列的刪除與改名同一視覺語彙：`AppButton` `icon`＋`trash`，名稱走 `aria-label` 與 `title`（locale 既有 `documents.folders.delete`）。
- 點下去仍先開 `useConfirm`／`ConfirmDialog`（既有「確定刪除資料夾「{name}」？資料夾內的文件會變成未分類」），不得改成立即刪除。
- 這是 D18「誤點會掉資料的動作留文字」的明確例外：刪資料夾不會刪文件本體，只是取消分類；列上同時有改名 icon，文字「刪除」破壞該列密度。
- 例外只限資料夾列。文件列選單刪除、審題批次丟棄、題庫丟棄等仍依 D18 保留文字確認。

## 理由

- 使用者直接指定列上改 icon、按下後確認；資料夾刪除的後果比刪文件輕，且畫面已有確認 widget。
- 列上「刪除」兩個字會把資料夾名稱與計數擠窄，也與同列改名 icon 不一致。

## 影響

- `docs/frontend.md` 文件區資料夾列、設計節制原則 D18 補上本例外。
- 實作：`DocumentFolderSidebar` 的刪除鈕改 icon-only；確認流程不變。
