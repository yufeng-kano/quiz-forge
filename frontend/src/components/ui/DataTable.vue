<script setup lang="ts" generic="T">
import { computed, ref } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import { APP_LOCALE, useAppI18n } from '@/i18n'
import AppIcon from './AppIcon.vue'
import AppSkeleton from './AppSkeleton.vue'
import type { DataTableColumn, DataTableSortDirection } from './dataTable'

/**
 * Generic table of the design system.
 *
 * It owns presentation only — hover rows, a sticky header, horizontal scroll
 * containment, skeleton and empty states, and client-side sorting on the
 * columns that provide a `sortValue`. It never fetches: rows come in as a
 * prop, so the same component serves the document list, 任務中心 and anything
 * later.
 *
 * Sorting is client-side on purpose: every list that uses this table is a
 * bounded page of rows already in memory (`limit` on the server side), so
 * re-querying to reorder them would only add latency.
 */
const props = withDefaults(
  defineProps<{
    columns: readonly DataTableColumn<T>[]
    rows: readonly T[]
    rowKey: (row: T) => string | number
    /** First load only; a background refresh keeps the current rows on screen. */
    loading?: boolean
    skeletonRowCount?: number
    /** Shown instead of rows once a load has finished with nothing to show. */
    emptyTitle?: string
    /** Rows react to hover and emit `rowClick`; the caller still provides a real link in a cell. */
    clickableRows?: boolean
    /**
     * Rows can be picked up and dropped somewhere else on the page. The table
     * only marks them `draggable` and forwards `rowDragStart` — what travels in
     * the `DataTransfer` is the caller's business, since only it knows what a
     * row means (see the 文件庫 folder column).
     */
    draggableRows?: boolean
    /**
     * Stretch to the parent pane and scroll internally. Used by the documents
     * workspace so a short list still fills the remaining viewport. Off by
     * default: other pages keep growing with content, then clamp at
     * `--data-table-max-height`.
     */
    fillHeight?: boolean
  }>(),
  {
    loading: false,
    skeletonRowCount: 5,
    clickableRows: false,
    draggableRows: false,
    fillHeight: false,
  },
)

const emit = defineEmits<{ rowClick: [row: T]; rowDragStart: [row: T, event: DragEvent] }>()

const { t } = useAppI18n()

const sortKey = ref<string | null>(null)
const sortDirection = ref<DataTableSortDirection>('asc')

const sortColumn = computed<DataTableColumn<T> | null>(() => {
  const key = sortKey.value
  if (key === null) {
    return null
  }
  return props.columns.find((column) => column.key === key) ?? null
})

/** `null` sorts after every real value, whichever direction is active. */
function compareValues(a: string | number | null, b: string | number | null): number {
  if (a === null && b === null) {
    return 0
  }
  if (a === null) {
    return 1
  }
  if (b === null) {
    return -1
  }
  if (typeof a === 'number' && typeof b === 'number') {
    return a - b
  }
  return String(a).localeCompare(String(b), APP_LOCALE)
}

const visibleRows = computed<readonly T[]>(() => {
  const sortValue = sortColumn.value?.sortValue
  if (sortValue === undefined) {
    return props.rows
  }
  const factor = sortDirection.value === 'asc' ? 1 : -1
  // Decorate once: `sortValue` may format a value, and calling it inside the
  // comparator would run it O(n log n) times per row instead of once.
  const decorated = props.rows.map((row) => ({ row, value: sortValue(row) }))
  decorated.sort((a, b) => {
    const result = compareValues(a.value, b.value)
    // A null always stays at the bottom, so the direction is not applied to it.
    return a.value === null || b.value === null ? result : result * factor
  })
  return decorated.map((entry) => entry.row)
})

function toggleSort(column: DataTableColumn<T>): void {
  if (column.sortValue === undefined) {
    return
  }
  if (sortKey.value === column.key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = column.key
  sortDirection.value = 'asc'
}

function ariaSortOf(column: DataTableColumn<T>): 'ascending' | 'descending' | 'none' | undefined {
  if (column.sortValue === undefined) {
    return undefined
  }
  if (sortKey.value !== column.key) {
    return 'none'
  }
  return sortDirection.value === 'asc' ? 'ascending' : 'descending'
}

const skeletonRows = computed(() => Array.from({ length: props.skeletonRowCount }, (_, i) => i))

const showEmpty = computed(() => !props.loading && props.rows.length === 0)

function onRowClick(row: T): void {
  if (props.clickableRows) {
    emit('rowClick', row)
  }
}

function onRowDragStart(row: T, event: DragEvent): void {
  if (props.draggableRows) {
    emit('rowDragStart', row, event)
  }
}
</script>

<template>
  <div class="data-table" :class="{ 'data-table--fill': props.fillHeight }">
    <div class="data-table__scroll">
      <table class="data-table__table">
        <thead>
          <tr>
            <th
              v-for="column in props.columns"
              :key="column.key"
              scope="col"
              :style="column.width === undefined ? undefined : { width: column.width }"
              :class="[
                `data-table__cell--${column.align ?? 'start'}`,
                { 'data-table__cell--nowrap': column.nowrap },
              ]"
              :aria-sort="ariaSortOf(column)"
            >
              <button
                v-if="column.sortValue !== undefined"
                class="data-table__sort"
                type="button"
                @click="toggleSort(column)"
              >
                <span :class="{ 'data-table__sr-only': column.labelHidden }">
                  {{ column.label }}
                </span>
                <AppIcon
                  v-if="sortKey === column.key"
                  :name="sortDirection === 'asc' ? 'chevronUp' : 'chevronDown'"
                  :size="14"
                />
              </button>
              <span v-else :class="{ 'data-table__sr-only': column.labelHidden }">
                {{ column.label }}
              </span>
            </th>
          </tr>
        </thead>

        <tbody v-if="props.loading && props.rows.length === 0">
          <tr v-for="index in skeletonRows" :key="`skeleton-${index}`">
            <td v-for="column in props.columns" :key="column.key">
              <AppSkeleton />
            </td>
          </tr>
        </tbody>

        <tbody v-else-if="showEmpty">
          <tr>
            <td class="data-table__empty" :colspan="props.columns.length">
              <slot name="empty">
                <EmptyState :title="props.emptyTitle ?? t('table.emptyTitle')" />
              </slot>
            </td>
          </tr>
        </tbody>

        <tbody v-else>
          <tr
            v-for="row in visibleRows"
            :key="props.rowKey(row)"
            :class="{
              'data-table__row--clickable': props.clickableRows,
              'data-table__row--draggable': props.draggableRows,
            }"
            :draggable="props.draggableRows"
            @click="onRowClick(row)"
            @dragstart="onRowDragStart(row, $event)"
          >
            <td
              v-for="column in props.columns"
              :key="column.key"
              :class="[
                `data-table__cell--${column.align ?? 'start'}`,
                { 'data-table__cell--nowrap': column.nowrap },
              ]"
            >
              <slot :name="column.key" :row="row">
                <span v-if="column.ellipsis" class="text-ellipsis" :title="column.value?.(row)">
                  {{ column.value?.(row) ?? '' }}
                </span>
                <template v-else>{{ column.value?.(row) ?? '' }}</template>
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.data-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
  overflow: hidden;
}

/* In a workspace the table is not a card standing next to the sidebar: the
   filter row above it and the table are one work surface, so the frame and the
   radius go away and the header's own bottom rule does the dividing
   (docs/frontend.md 視覺風格 / 設計節制原則 D16). */
.data-table--fill {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-self: stretch;
  min-height: 0;
  height: 100%;
  border: none;
  border-radius: 0;
}

/* The scroll container is the table's own box: it keeps a wide table from
   pushing the page sideways, and it is what the sticky header sticks to. */
.data-table__scroll {
  overflow: auto;
  /* Leaves room for the page header and whatever sits above the table, but
     never shrinks so far that only a row or two is visible. A page with more
     above the table raises `--data-table-max-height` itself. */
  max-height: var(--data-table-max-height, max(22rem, calc(100vh - 18rem)));
}

.data-table--fill .data-table__scroll {
  flex: 1;
  min-height: 0;
  max-height: none;
}

.data-table__table {
  width: 100%;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
  font-size: var(--font-size-md);
}

/* Header text stays at the table's own size: weight, the shell background and
   the rule under it already separate it from the rows, so it does not have to
   be shrunk and greyed as well (docs/frontend.md 設計節制原則 D20). */
.data-table__table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-shell);
  color: var(--color-heading);
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}

.data-table__table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-hairline);
  vertical-align: middle;
  overflow: hidden;
}

.data-table__table tbody tr:last-child td {
  border-bottom: none;
}

.data-table__table tbody tr:hover {
  background: var(--color-background-soft);
}

.data-table__row--clickable {
  cursor: pointer;
}

/* A draggable row that is also clickable keeps the pointer cursor: the grab
   affordance would promise dragging is the only thing a row does */
.data-table__row--draggable:not(.data-table__row--clickable) {
  cursor: grab;
}

.data-table__cell--end {
  text-align: right;
}

.data-table__cell--nowrap {
  white-space: nowrap;
}

.data-table__sort {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.data-table__sort:hover {
  color: var(--color-accent);
}

.data-table__empty {
  padding: 0;
  border-bottom: none;
}

.data-table--fill .data-table__table:has(.data-table__empty) {
  height: 100%;
}

.data-table--fill tbody:has(.data-table__empty) {
  height: 100%;
}

.data-table--fill .data-table__empty {
  height: 100%;
  vertical-align: middle;
}

.data-table__sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
