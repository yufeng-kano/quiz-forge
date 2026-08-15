/**
 * Question state for 審題 (`/review`) and 題庫 (`/questions`).
 *
 * One store holds both lists because they are two views of the same rows and
 * every state change moves a question between them: approving a draft takes it
 * out of the review queue and into the bank, discarding a bank question takes
 * it back out. `reconcile()` is the single place that decision is made, so a
 * card never has to guess whether it should still be on screen.
 *
 * The filters and the page of both lists live here too (docs/frontend.md: 篩選
 * 條件放 Pinia store), so leaving a page and coming back keeps the same view.
 * Both lists ask for an explicit `limit`/`offset` and keep the envelope's
 * `total`, which is what the pagination controls and the counts are built from
 * — a list is never silently cut off at the server's default page size.
 *
 * Read failures are stored (`draftsError` / `bankError`) because the list still
 * renders around them; the mutating actions throw, so the caller that triggered
 * one decides how to report it (a toast, or a message next to its own buttons).
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  QUESTIONS_PAGE_SIZE,
  approveQuestion,
  createQuestion,
  duplicateQuestion,
  listQuestions,
  patchQuestion,
  rejectQuestion,
  type QuestionCreateRequest,
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
  /** Free text sent as `q`; empty means no search. */
  search: string
}

/** The review queue narrows on the two properties a draft carries by itself. */
export interface QuestionDraftFilters {
  type: QuestionType | null
  difficulty: string | null
}

function emptyFilters(): QuestionBankFilters {
  return { type: null, difficulty: null, subjectId: null, categoryId: null, search: '' }
}

function emptyDraftFilters(): QuestionDraftFilters {
  return { type: null, difficulty: null }
}

interface LoadOptions {
  /** Refresh without clearing the list or showing the loading state. */
  silent?: boolean
}

/** Page count for a total, never below one so the controls always have a page. */
function pageCountOf(total: number): number {
  return Math.max(1, Math.ceil(total / QUESTIONS_PAGE_SIZE))
}

export const useQuestionsStore = defineStore('questions', () => {
  const drafts = ref<QuestionListItem[]>([])
  const draftsLoading = ref(false)
  const draftsError = ref<string | null>(null)
  const draftsLoaded = ref(false)
  const draftsTotal = ref(0)
  const draftsOffset = ref(0)
  const draftFilters = ref<QuestionDraftFilters>(emptyDraftFilters())

  const bank = ref<QuestionListItem[]>([])
  const bankLoading = ref(false)
  const bankError = ref<string | null>(null)
  const bankLoaded = ref(false)
  const bankTotal = ref(0)
  const bankOffset = ref(0)

  const filters = ref<QuestionBankFilters>(emptyFilters())

  /** How many of the queue/bank are on screen right now. */
  const draftCount = computed(() => drafts.value.length)
  const bankCount = computed(() => bank.value.length)

  const draftsPage = computed(() => Math.floor(draftsOffset.value / QUESTIONS_PAGE_SIZE) + 1)
  const draftsPageCount = computed(() => pageCountOf(draftsTotal.value))
  const bankPage = computed(() => Math.floor(bankOffset.value / QUESTIONS_PAGE_SIZE) + 1)
  const bankPageCount = computed(() => pageCountOf(bankTotal.value))

  const hasActiveFilter = computed(() => {
    const current = filters.value
    return (
      current.type !== null ||
      current.difficulty !== null ||
      current.categoryId !== null ||
      current.search !== ''
    )
  })

  const hasActiveDraftFilter = computed(
    () => draftFilters.value.type !== null || draftFilters.value.difficulty !== null,
  )

  function draftQuery(): QuestionListQuery {
    const current = draftFilters.value
    const query: QuestionListQuery = {
      status: 'draft',
      limit: QUESTIONS_PAGE_SIZE,
      offset: draftsOffset.value,
    }
    if (current.type !== null) {
      query.type = current.type
    }
    if (current.difficulty !== null) {
      query.difficulty = current.difficulty
    }
    return query
  }

  async function loadDrafts(options: LoadOptions = {}): Promise<void> {
    const silent = options.silent ?? false
    if (!silent) {
      draftsLoading.value = true
    }
    try {
      let page = await listQuestions(draftQuery())
      // The page can fall off the end of the result while it is open (a batch
      // adopted everything on it), which would leave an empty list next to
      // page controls claiming there is something here. Fall back to the last
      // page that does exist.
      if (page.items.length === 0 && draftsOffset.value > 0 && page.total > 0) {
        draftsOffset.value = (pageCountOf(page.total) - 1) * QUESTIONS_PAGE_SIZE
        page = await listQuestions(draftQuery())
      }
      drafts.value = page.items
      draftsTotal.value = page.total
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
    const query: QuestionListQuery = {
      status: 'approved',
      limit: QUESTIONS_PAGE_SIZE,
      offset: bankOffset.value,
    }
    if (current.type !== null) {
      query.type = current.type
    }
    if (current.difficulty !== null) {
      query.difficulty = current.difficulty
    }
    if (current.categoryId !== null) {
      query.category_id = current.categoryId
    }
    if (current.search !== '') {
      query.q = current.search
    }
    return query
  }

  async function loadBank(options: LoadOptions = {}): Promise<void> {
    const silent = options.silent ?? false
    if (!silent) {
      bankLoading.value = true
    }
    try {
      let page = await listQuestions(bankQuery())
      // Same fallback as the review queue: a page that no longer exists (rows
      // discarded, filter narrowed) drops back to the last one that does.
      if (page.items.length === 0 && bankOffset.value > 0 && page.total > 0) {
        bankOffset.value = (pageCountOf(page.total) - 1) * QUESTIONS_PAGE_SIZE
        page = await listQuestions(bankQuery())
      }
      bank.value = page.items
      bankTotal.value = page.total
      bankLoaded.value = true
      bankError.value = null
    } catch (error) {
      bankError.value = translateApiError(error)
    } finally {
      bankLoading.value = false
    }
  }

  /** A new query always starts at the first page: an offset into the old result means nothing. */
  function setFilters(next: QuestionBankFilters): void {
    filters.value = next
    bankOffset.value = 0
  }

  function resetFilters(): void {
    setFilters(emptyFilters())
  }

  function setDraftFilters(next: QuestionDraftFilters): void {
    draftFilters.value = next
    draftsOffset.value = 0
  }

  function resetDraftFilters(): void {
    setDraftFilters(emptyDraftFilters())
  }

  function setBankPage(page: number): void {
    const clamped = Math.min(Math.max(1, page), bankPageCount.value)
    bankOffset.value = (clamped - 1) * QUESTIONS_PAGE_SIZE
  }

  function setDraftsPage(page: number): void {
    const clamped = Math.min(Math.max(1, page), draftsPageCount.value)
    draftsOffset.value = (clamped - 1) * QUESTIONS_PAGE_SIZE
  }

  /**
   * Put the server's own version of a question back into both lists: it stays
   * where its new status belongs and leaves the other list. A row that is not
   * in a list is not inserted — the bank only shows what its current filters
   * matched, and re-running that query is `loadBank()`'s job.
   */
  function reconcile(item: QuestionListItem): void {
    const wasDraft = drafts.value.some((existing) => existing.id === item.id)
    const wasInBank = bank.value.some((existing) => existing.id === item.id)
    drafts.value = applyStatus(drafts.value, item, item.status === 'draft')
    bank.value = applyStatus(bank.value, item, item.status === 'approved')
    // A row that left a list also left the result its total counts.
    if (wasDraft && item.status !== 'draft') {
      draftsTotal.value = Math.max(0, draftsTotal.value - 1)
    }
    if (wasInBank && item.status !== 'approved') {
      bankTotal.value = Math.max(0, bankTotal.value - 1)
    }
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

  /**
   * Manual authoring. The new row is not spliced into a list: whether it
   * belongs there depends on the current filters, so the caller refreshes the
   * list its status landed in.
   */
  async function create(request: QuestionCreateRequest): Promise<QuestionListItem> {
    return await createQuestion(request)
  }

  /** Copy a question; the copy is always a `draft`, i.e. it lands on 審題. */
  async function duplicate(questionId: number): Promise<QuestionListItem> {
    return await duplicateQuestion(questionId)
  }

  return {
    drafts,
    draftsLoading,
    draftsError,
    draftsLoaded,
    draftsTotal,
    draftsPage,
    draftsPageCount,
    draftCount,
    draftFilters,
    hasActiveDraftFilter,
    bank,
    bankLoading,
    bankError,
    bankLoaded,
    bankCount,
    bankTotal,
    bankPage,
    bankPageCount,
    filters,
    hasActiveFilter,
    loadDrafts,
    loadBank,
    setFilters,
    resetFilters,
    setDraftFilters,
    resetDraftFilters,
    setBankPage,
    setDraftsPage,
    approve,
    reject,
    updatePayload,
    create,
    duplicate,
  }
})
