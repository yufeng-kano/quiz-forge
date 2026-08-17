# 文件庫工作區左右貼齊頁首底線

同日 L6 寫「貼到內容區左右緣、頁面 `--content-padding-x` 那層即可」。落地後使用者標出的左右紅框仍在：那兩條空帶就是 `.page` 的水平 gutter，工作區沒有像 `PageHeader` 一樣用負 margin 吃掉它，資料夾欄與表格比頁首底線各縮進一截。

## 決策

### L8. 工作區左右出血，與頁首底線同寬

- `.workspace` 用與 `PageHeader` 相同的水平負 margin（`calc(-1 * var(--content-padding-x))`），左右貼齊 `.app-main`，不要再縮在 page gutter 裡面。
- 分割線仍在兩欄中間，線兩側不加空白帶（L6 中段仍有效）。
- 資料夾列文字、搜尋列、表頭儲存格自己的內距留下，讓字不貼邊；不得再加一層等同 page gutter 的外框 padding，否則紅框會回來。
- 只改文件庫這塊工作區。任務中心、題庫不要順手出血。

## 理由

- 頁首底線已經全寬，工作區卻縮在 gutter 裡，左右各留一條什麼都沒有的白帶。使用者要的是拿掉那兩條，不是再退一層。
- L6 的「那層即可」把 page gutter 當成終點，和截圖上的左右紅框衝突。本決策推翻 L6 對左右緣的那句，其餘（拿掉欄／表額外 gutter、搜尋列併入表格）維持。

## 影響

- `docs/frontend.md` 文件區版面補一句：工作區與頁首底線同寬。
- 實作：`DocumentListView` 的 `.workspace` 加水平負 margin。
