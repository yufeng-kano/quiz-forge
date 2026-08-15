/**
 * Word export state for `/exports`: the history list and the job created last.
 *
 * The history comes from `GET /api/v1/exports`, so it survives reloads on its
 * own; what the server does not remember is which job the user just started —
 * `POST /api/v1/exports` returns a job id and nothing else. Keeping that id
 * here (docs/frontend.md: 跨頁狀態放 Pinia store) means leaving the page while a
 * paper renders and coming back still shows its progress, picked up again by
 * `useJobPolling`.
 *
 * Read failures are stored because the rest of the page still renders around
 * them; `submit()` throws so the form can show the message next to its button.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { createExportJob, listExports, type ExportListItem, type PaperSize } from '@/api'
import { translateApiError } from '@/i18n/errors'

export interface ExportJobEntry {
  jobId: number
  paperSize: PaperSize
  questionCount: number
  /** ISO timestamp of the submission, formatted for display by the view. */
  submittedAt: string
  /**
   * Whether the "it finished" follow-up (refresh the history, drop the
   * selection that was just exported) has already run. The job itself stays
   * `done` forever, so without this flag returning to the page would clear a
   * selection made after the export.
   */
  settled: boolean
}

interface LoadOptions {
  /** Refresh without showing the loading state, keeping the current list up. */
  silent?: boolean
}

export const useExportsStore = defineStore('exports', () => {
  /** Newest first, as the backend orders it. */
  const history = ref<ExportListItem[]>([])
  const historyLoading = ref(false)
  const historyError = ref<string | null>(null)
  const historyLoaded = ref(false)

  /** The export job started last in this session, or null if there is none. */
  const currentJob = ref<ExportJobEntry | null>(null)

  async function loadHistory(options: LoadOptions = {}): Promise<void> {
    const silent = options.silent ?? false
    if (!silent) {
      historyLoading.value = true
    }
    try {
      history.value = await listExports()
      historyLoaded.value = true
      historyError.value = null
    } catch (error) {
      historyError.value = translateApiError(error)
    } finally {
      historyLoading.value = false
    }
  }

  async function submit(questionIds: readonly number[], paperSize: PaperSize): Promise<number> {
    const result = await createExportJob({
      question_ids: [...questionIds],
      paper_size: paperSize,
    })
    currentJob.value = {
      jobId: result.job_id,
      paperSize,
      questionCount: questionIds.length,
      submittedAt: new Date().toISOString(),
      settled: false,
    }
    return result.job_id
  }

  /** Records that the current job's completion has been dealt with. */
  function markCurrentJobSettled(): void {
    const entry = currentJob.value
    if (entry !== null) {
      currentJob.value = { ...entry, settled: true }
    }
  }

  return {
    history,
    historyLoading,
    historyError,
    historyLoaded,
    currentJob,
    loadHistory,
    submit,
    markCurrentJobSettled,
  }
})
