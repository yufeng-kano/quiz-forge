/**
 * Shared shape of the 出題 scope widgets (文件 / 分類).
 *
 * Both fields are built the same way — a trigger button, removable chips, and a
 * modal picker with its own search box (docs/frontend.md 清單有界原則) — so the
 * chip type lives here instead of being declared twice. The matching itself is
 * `@/utils/search`, shared with the 文件 list.
 */

/** One picked item as a scope field renders it. */
export interface ScopeChip {
  id: number
  /** Single-line text of the chip; also its `title` tooltip. */
  label: string
}
