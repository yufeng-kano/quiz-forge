/**
 * Column definitions for `DataTable.vue`.
 *
 * A column always carries its already-localised `label` (the table itself
 * resolves no locale keys) and renders either through the named slot
 * `#[key]="{ row }"` or, when the value is plain text, through `value`.
 *
 * A column is sortable exactly when it provides `sortValue`: there is no
 * separate `sortable` flag that could disagree with it, and a generic table
 * cannot guess how to order an arbitrary row shape.
 */

export type DataTableSortDirection = 'asc' | 'desc'

export interface DataTableColumn<T> {
  /** Unique within the table; also the name of the cell slot. */
  readonly key: string
  /** Localised header text. */
  readonly label: string
  /** Plain-text cell content, used when no `#[key]` slot is given. */
  readonly value?: (row: T) => string
  /** Providing this makes the column sortable; `null` sorts last. */
  readonly sortValue?: (row: T) => string | number | null
  /** `end` right-aligns numeric columns and action buttons. */
  readonly align?: 'start' | 'end'
  /** CSS width for the column (e.g. `'8rem'`), left to the browser when absent. */
  readonly width?: string
  /** Keep the cell on one line (ids, timestamps, status pills). */
  readonly nowrap?: boolean
  /** Header text is for assistive technology only (action columns). */
  readonly labelHidden?: boolean
}
