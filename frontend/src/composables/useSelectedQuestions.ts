/**
 * Resolves the export selection (ids only) into the approved questions behind
 * it.
 *
 * The selection store deliberately holds ids and nothing else, so 匯出 has to
 * look the rows up. It does that by walking the approved list in pages of
 * `QUESTIONS_LIST_LIMIT_MAX` — the largest page the server allows — and stops
 * as soon as every selected id has been found, so the common case is one
 * request. Asking per id would be one request per question; asking without a
 * limit would silently stop at the server's default page and make anything
 * beyond it look as though it had left the approved range.
 *
 * An id that is genuinely not in the approved list stays `null`, which is what
 * the page shows as 「已不在已採用題庫」: it is exactly what would make the
 * export job fail (docs/export.md — 全部必須 `approved`).
 */

import { computed, onMounted, ref, watch, type ComputedRef, type Ref } from 'vue'

import {
  QUESTIONS_LIST_LIMIT_MAX,
  isQuestionType,
  listQuestions,
  type QuestionListItem,
  type QuestionType,
} from '@/api'
import { translateApiError } from '@/i18n/errors'
import { useExportSelectionStore } from '@/stores/exportSelection'

export interface SelectedQuestionRow {
  id: number
  /** `null` once loading has finished means the id is no longer approved. */
  question: QuestionListItem | null
}

export interface UseSelectedQuestionsResult {
  rows: ComputedRef<SelectedQuestionRow[]>
  /** The question types present in the selection, in the fixed type order. */
  types: ComputedRef<QuestionType[]>
  loading: Ref<boolean>
  loadError: Ref<string | null>
  loaded: Ref<boolean>
  reload: () => Promise<void>
}

export function useSelectedQuestions(): UseSelectedQuestionsResult {
  const selection = useExportSelectionStore()

  const found = ref<Map<number, QuestionListItem>>(new Map())
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const loaded = ref(false)

  const rows = computed<SelectedQuestionRow[]>(() =>
    selection.selectedIds.map((id) => ({ id, question: found.value.get(id) ?? null })),
  )

  const types = computed<QuestionType[]>(() => {
    const present = new Set<QuestionType>()
    for (const row of rows.value) {
      const type = row.question?.type
      if (type !== undefined && isQuestionType(type)) {
        present.add(type)
      }
    }
    return [...present]
  })

  async function load(options: { silent?: boolean } = {}): Promise<void> {
    const wanted = new Set(selection.selectedIds)
    if (wanted.size === 0) {
      found.value = new Map()
      loaded.value = true
      loadError.value = null
      return
    }
    if (!(options.silent ?? false)) {
      loading.value = true
    }
    try {
      const collected = new Map<number, QuestionListItem>()
      let offset = 0
      let total = Number.POSITIVE_INFINITY
      while (offset < total && collected.size < wanted.size) {
        const page = await listQuestions({
          status: 'approved',
          limit: QUESTIONS_LIST_LIMIT_MAX,
          offset,
        })
        total = page.total
        for (const question of page.items) {
          if (wanted.has(question.id)) {
            collected.set(question.id, question)
          }
        }
        if (page.items.length === 0) {
          break
        }
        offset += page.items.length
      }
      found.value = collected
      loaded.value = true
      loadError.value = null
    } catch (error) {
      loadError.value = translateApiError(error)
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    void load()
  })

  // Coming back from 題庫 with newly picked questions: resolve the new ids
  // without blanking the rows already on screen.
  watch(
    () => selection.selectedIds,
    (ids) => {
      if (loaded.value && ids.some((id) => !found.value.has(id))) {
        void load({ silent: true })
      }
    },
  )

  return { rows, types, loading, loadError, loaded, reload: () => load() }
}
