/**
 * Which approved questions are queued for the Word export, and what each one
 * scores on this paper.
 *
 * The selection is made on 題庫 (`/questions`) and consumed on 匯出
 * (`/exports`), so it has to survive navigation — exactly the cross-page state
 * docs/frontend.md puts in Pinia. It holds ids and per-question points only:
 * the question rows themselves are refetched by whichever page needs them, so a
 * title edited in between is never shown stale.
 *
 * The per-question points live here rather than on the 匯出 page because they
 * share the selection's lifetime: they describe this one paper, they die with
 * `clear()`, and a question that leaves the selection takes its override along
 * (a key outside `question_ids` is a 422 on submit). As page-local state they
 * were silently wiped by a round trip to 題庫
 * (docs/decisions/2026-08-17-professional-form-pages.md D30). They are not
 * persisted to localStorage — a week later they would score a different
 * selection; the per-type defaults in `exportPrefs` are the remembered habit.
 *
 * The order ids were picked in is preserved, which is the order the export page
 * gets them in.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useExportSelectionStore = defineStore('exportSelection', () => {
  const selectedIds = ref<number[]>([])
  /** Per-question point overrides for the current paper, keyed by question id. */
  const questionPoints = ref<Record<number, number>>({})

  /** Membership lookup for a list render, so it stays O(1) per row. */
  const selectedIdSet = computed(() => new Set(selectedIds.value))
  const count = computed(() => selectedIds.value.length)

  function isSelected(questionId: number): boolean {
    return selectedIdSet.value.has(questionId)
  }

  /** Drops the overrides whose question is no longer in `selectedIds`. */
  function prunePoints(): void {
    const kept: Record<number, number> = {}
    for (const id of selectedIds.value) {
      const points = questionPoints.value[id]
      if (points !== undefined) {
        kept[id] = points
      }
    }
    if (Object.keys(kept).length !== Object.keys(questionPoints.value).length) {
      questionPoints.value = kept
    }
  }

  function select(questionId: number): void {
    if (!isSelected(questionId)) {
      selectedIds.value = [...selectedIds.value, questionId]
    }
  }

  function deselect(questionId: number): void {
    selectedIds.value = selectedIds.value.filter((id) => id !== questionId)
    prunePoints()
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
    prunePoints()
  }

  /** True only when every given id is selected and there is at least one. */
  function areAllSelected(questionIds: readonly number[]): boolean {
    if (questionIds.length === 0) {
      return false
    }
    const known = selectedIdSet.value
    return questionIds.every((id) => known.has(id))
  }

  /** `null` points removes the override, so the question follows its type. */
  function setQuestionPoints(questionId: number, points: number | null): void {
    const next = { ...questionPoints.value }
    if (points === null) {
      delete next[questionId]
    } else {
      next[questionId] = points
    }
    questionPoints.value = next
  }

  /** Wholesale rewrite, used by 依目標總分平均分配; pruned to the selection. */
  function replaceQuestionPoints(points: Readonly<Record<number, number>>): void {
    const next: Record<number, number> = {}
    for (const id of selectedIds.value) {
      const value = points[id]
      if (value !== undefined) {
        next[id] = value
      }
    }
    questionPoints.value = next
  }

  function clearQuestionPoints(): void {
    questionPoints.value = {}
  }

  function clear(): void {
    selectedIds.value = []
    questionPoints.value = {}
  }

  return {
    selectedIds,
    selectedIdSet,
    questionPoints,
    count,
    isSelected,
    select,
    deselect,
    toggle,
    selectMany,
    deselectMany,
    areAllSelected,
    setQuestionPoints,
    replaceQuestionPoints,
    clearQuestionPoints,
    clear,
  }
})
