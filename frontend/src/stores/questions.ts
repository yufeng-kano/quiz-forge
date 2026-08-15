/**
 * Question state for 審題 (`/review`) and 題庫 (`/questions`).
 *
 * One store holds both lists because they are two views of the same rows and
 * every state change moves a question between them: approving a draft takes it
 * out of the review queue and into the bank, discarding a bank question takes
 * it back out. `reconcile()` is the single place that decision is made, so a
 * card never has to guess whether it should still be on screen.
 *
 * The bank filters live here too (docs/frontend.md: 篩選條件放 Pinia store), so
 * leaving the page and coming back keeps the same view.
 *
 * Read failures are stored (`draftsError` / `bankError`) because the list still
 * renders around them; the mutating actions throw, so the card that triggered
 * one shows the message next to its own buttons.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  approveQuestion,
  listQuestions,
  patchQuestion,
  rejectQuestion,
  type QuestionListItem,
  type QuestionListQuery,
  type QuestionPayload,
  type QuestionType,
} from '@/api'
import { translateApiError } from '@/i18n/errors'

export interface QuestionBankFilters {
  type: QuestionType | null
  difficulty: string | null
  /** Only narrows the topic choices; the request filters on `categoryId`. */
  subjectId: number | null
  /**
   * The category actually sent as `category_id`. Chunks are always classified
   * at topic level (`backend.ingestion.pipeline`), so this is a topic id.
   */
  categoryId: number | null
}

function emptyFilters(): QuestionBankFilters {
  return { type: null, difficulty: null, subjectId: null, categoryId: null }
}

interface LoadOptions {
  /** Refresh without clearing the list or showing the loading state. */
  silent?: boolean
}

export const useQuestionsStore = defineStore('questions', () => {
  const drafts = ref<QuestionListItem[]>([])
  const draftsLoading = ref(false)
  const draftsError = ref<string | null>(null)
  const draftsLoaded = ref(false)

  const bank = ref<QuestionListItem[]>([])
  const bankLoading = ref(false)
  const bankError = ref<string | null>(null)
  const bankLoaded = ref(false)

  const filters = ref<QuestionBankFilters>(emptyFilters())

  const draftCount = computed(() => drafts.value.length)
  const bankCount = computed(() => bank.value.length)
  const hasActiveFilter = computed(() => {
    const current = filters.value
    return current.type !== null || current.difficulty !== null || current.categoryId !== null
  })

  async function loadDrafts(options: LoadOptions = {}): Promise<void> {
    const silent = options.silent ?? false
    if (!silent) {
      draftsLoading.value = true
    }
    try {
      drafts.value = await listQuestions({ status: 'draft' })
      draftsLoaded.value = true
      draftsError.value = null
    } catch (error) {
      draftsError.value = translateApiError(error)
    } finally {
      draftsLoading.value = false
    }
  }

  function bankQuery(): QuestionListQuery {
    const current = filters.value
    const query: QuestionListQuery = { status: 'approved' }
    if (current.type !== null) {
      query.type = current.type
    }
    if (current.difficulty !== null) {
      query.difficulty = current.difficulty
    }
    if (current.categoryId !== null) {
      query.category_id = current.categoryId
    }
    return query
  }

  async function loadBank(options: LoadOptions = {}): Promise<void> {
    const silent = options.silent ?? false
    if (!silent) {
      bankLoading.value = true
    }
    try {
      bank.value = await listQuestions(bankQuery())
      bankLoaded.value = true
      bankError.value = null
    } catch (error) {
      bankError.value = translateApiError(error)
    } finally {
      bankLoading.value = false
    }
  }

  function setFilters(next: QuestionBankFilters): void {
    filters.value = next
  }

  function resetFilters(): void {
    filters.value = emptyFilters()
  }

  /**
   * Put the server's own version of a question back into both lists: it stays
   * where its new status belongs and leaves the other list. A row that is not
   * in a list is not inserted — the bank only shows what its current filters
   * matched, and re-running that query is `loadBank()`'s job.
   */
  function reconcile(item: QuestionListItem): void {
    drafts.value = applyStatus(drafts.value, item, item.status === 'draft')
    bank.value = applyStatus(bank.value, item, item.status === 'approved')
  }

  function applyStatus(
    list: QuestionListItem[],
    item: QuestionListItem,
    belongs: boolean,
  ): QuestionListItem[] {
    const index = list.findIndex((existing) => existing.id === item.id)
    if (index === -1) {
      return list
    }
    if (!belongs) {
      return list.filter((existing) => existing.id !== item.id)
    }
    const next = [...list]
    next.splice(index, 1, item)
    return next
  }

  async function approve(questionId: number): Promise<QuestionListItem> {
    const updated = await approveQuestion(questionId)
    reconcile(updated)
    return updated
  }

  async function reject(questionId: number): Promise<QuestionListItem> {
    const updated = await rejectQuestion(questionId)
    reconcile(updated)
    return updated
  }

  async function updatePayload(
    questionId: number,
    payload: QuestionPayload,
  ): Promise<QuestionListItem> {
    const updated = await patchQuestion(questionId, { payload })
    reconcile(updated)
    return updated
  }

  return {
    drafts,
    draftsLoading,
    draftsError,
    draftsLoaded,
    draftCount,
    bank,
    bankLoading,
    bankError,
    bankLoaded,
    bankCount,
    filters,
    hasActiveFilter,
    loadDrafts,
    loadBank,
    setFilters,
    resetFilters,
    approve,
    reject,
    updatePayload,
  }
})
