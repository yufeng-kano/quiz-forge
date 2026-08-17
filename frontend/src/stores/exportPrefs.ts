/**
 * The 匯出 form settings that outlive the browser session.
 *
 * A teacher builds papers the same way every time: the same sheet, the same
 * 表頭 columns, the same target total split the same way across question
 * types. Those are read back from `localStorage` when the store is created and
 * written again on every change, so reopening the browser reopens the form as
 * it was left (docs/frontend.md 匯出頁;
 * docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md D33).
 *
 * Deliberately not here: which questions are selected and what each one
 * scores (`exportSelection`). Both describe one particular paper rather than a
 * habit, and restoring them a week later would silently score a different
 * selection.
 *
 * A refused or corrupt store is not an error state anyone can act on, so the
 * defaults simply take over — `parseExportPrefs` guarantees a usable value for
 * any input at all.
 */

import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

import type { ExportHeaderFields, PaperSize } from '@/api'
import {
  EXPORT_PREFS_STORAGE_KEY,
  parseExportPrefs,
  type ExportPrefs,
  type ExportTypePercents,
} from '@/export/prefs'
import { readStoredValue, writeStoredValue } from '@/utils/storage'

export const useExportPrefsStore = defineStore('exportPrefs', () => {
  const restored = parseExportPrefs(readStoredValue(EXPORT_PREFS_STORAGE_KEY))

  const paperSize = ref<PaperSize>(restored.paperSize)
  const headerFields = ref<ExportHeaderFields>(restored.headerFields)
  const targetTotal = ref<number>(restored.targetTotal)
  const typePercents = ref<ExportTypePercents>(restored.typePercents)

  /**
   * One writer for all four. `deep` covers a caller that changes a single
   * 表頭 column or one type's percentage in place instead of replacing the
   * object, so no edit can be persisted only by accident of how it was made.
   */
  watch(
    [paperSize, headerFields, targetTotal, typePercents],
    () => {
      const prefs: ExportPrefs = {
        paperSize: paperSize.value,
        headerFields: { ...headerFields.value },
        targetTotal: targetTotal.value,
        typePercents: { ...typePercents.value },
      }
      writeStoredValue(EXPORT_PREFS_STORAGE_KEY, prefs)
    },
    { deep: true },
  )

  return { paperSize, headerFields, targetTotal, typePercents }
})
