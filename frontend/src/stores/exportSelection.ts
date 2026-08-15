/**
 * Which approved questions are queued for the Word export.
 *
 * The selection is made on 題庫 (`/questions`) and consumed on 匯出
 * (`/exports`), so it has to survive navigation — exactly the cross-page state
 * docs/frontend.md puts in Pinia. It holds ids only: the question rows
 * themselves are refetched by whichever page needs them, so a title edited in
 * between is never shown stale.
 *
 * The order ids were picked in is preserved, which is the order the export page
 * gets them in.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useExportSelectionStore = defineStore('exportSelection', () => {
  const selectedIds = ref<number[]>([])

  /** Membership lookup for a list render, so it stays O(1) per row. */
  const selectedIdSet = computed(() => new Set(selectedIds.value))
  const count = computed(() => selectedIds.value.length)

  function isSelected(questionId: number): boolean {
    return selectedIdSet.value.has(questionId)
  }

  function select(questionId: number): void {
    if (!isSelected(questionId)) {
      selectedIds.value = [...selectedIds.value, questionId]
    }
  }

  function deselect(questionId: number): void {
    selectedIds.value = selectedIds.value.filter((id) => id !== questionId)
  }

  function toggle(questionId: number): void {
    if (isSelected(questionId)) {
      deselect(questionId)
    } else {
      select(questionId)
    }
  }

  /** Add every id not already selected, keeping the existing ones in place. */
  function selectMany(questionIds: readonly number[]): void {
    const known = selectedIdSet.value
    const added = questionIds.filter((id) => !known.has(id))
    if (added.length > 0) {
      selectedIds.value = [...selectedIds.value, ...added]
    }
  }

  function deselectMany(questionIds: readonly number[]): void {
    const removed = new Set(questionIds)
    selectedIds.value = selectedIds.value.filter((id) => !removed.has(id))
  }

  /** True only when every given id is selected and there is at least one. */
  function areAllSelected(questionIds: readonly number[]): boolean {
    if (questionIds.length === 0) {
      return false
    }
    const known = selectedIdSet.value
    return questionIds.every((id) => known.has(id))
  }

  function clear(): void {
    selectedIds.value = []
  }

  return {
    selectedIds,
    selectedIdSet,
    count,
    isSelected,
    select,
    deselect,
    toggle,
    selectMany,
    deselectMany,
    areAllSelected,
    clear,
  }
})
