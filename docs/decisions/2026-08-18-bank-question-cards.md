# 題庫題目列改框線卡片

同日 B3／B4 把題目列收緊、拿掉正解底色帶後，使用者澄清原意：「不 對 我是要題目是卡片的感覺」——最初那句話是要求把題庫題目**做成**卡片、卡片之間有間距，並指定「參考 overview 的資料統計」（總覽 `StatCard`：框線＋圓角＋底色的卡片）。B3／B4 建立在誤讀上，整份推翻。

## 決策

### C1. 題庫題目列是框線卡片

- 題庫（題庫與已選兩個檢視）的每題是一個卡片：`1px solid var(--color-border)` 框、`var(--radius-lg)` 圓角、`var(--color-background)` 底色、`var(--space-4)` 內距——與總覽 `StatCard` 同一語彙。
- 卡片之間 `var(--space-3)` 間距（同總覽卡片 grid 的 gap）。
- 卡片内的題目列不再自己畫 hairline 底線：卡框就是分隔。
- skeleton 列比照卡片樣式。
- 只限題庫頁：卡片樣式掛在題庫清單上，不改共用 `QuestionCard` 元件本身。

### C2. 推翻 B3／B4

- 恢復 `QuestionCard` 原本的垂直 padding（`--space-4`）與正解選項的底色帶（`--color-status-done-bg`）。
- `docs/decisions/2026-08-18-bank-question-rows-flat.md` 整份作廢；審題頁維持分隔列、不是卡片（D12 對審題的部分維持，對題庫的部分被 C1 推翻）。

## 理由

- 使用者明確要卡片感，對照物是總覽的統計卡片；「卡片不是版面骨架」的限制對題庫題目列由使用者要求解除，範圍只限題庫。
- 共用元件若直接改成卡片，審題頁會跟著變；使用者的要求只指名題庫，故卡片語彙落在題庫清單層。

## 影響

- `docs/frontend.md`：題目元件段撤掉 B3／B4 註記、視覺風格的「漂浮卡」限制補題庫例外。
- 實作：還原 `QuestionCard.vue`／`QuestionOptionList.vue` 的 B3／B4 改動；`QuestionBankView.vue` 清單層加卡片樣式與 gap。