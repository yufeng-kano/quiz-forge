/**
 * The 匯出 form settings that outlive the browser session.
 *
 * A teacher builds papers the same way every time: the same sheet, the same
 * 表頭 columns, the same points per question type. Those three are read back
 * from `localStorage` when the store is created and written again on every
 * change, so reopening the browser reopens the form as it was left
 * (docs/frontend.md 匯出頁).
 *
 * Deliberately not here: which questions are selected (`exportSelection`) and
 * the per-question point overrides. Both describe one particular paper rather
 * than a habit, and restoring them a week later would silently score a
 * different selection.
 *
 * A refused or corrupt store is not an error state anyone can act on, so the
 * defaults simply take over — `parseExportPrefs` guarantees a usable value for
 * any input at all.
 */

import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

import type { ExportHeaderFields, ExportPoints, PaperSize } from '@/api'
import { EXPORT_PREFS_STORAGE_KEY, parseExportPrefs, type ExportPrefs } from '@/export/prefs'
import { readStoredValue, writeStoredValue } from '@/utils/storage'

export const useExportPrefsStore = defineStore('exportPrefs', () => {
  const restored = parseExportPrefs(readStoredValue(EXPORT_PREFS_STORAGE_KEY))

  const paperSize = ref<PaperSize>(restored.paperSize)
  const headerFields = ref<ExportHeaderFields>(restored.headerFields)
  const typePoints = ref<ExportPoints>(restored.typePoints)

  /**
   * One writer for all three. `deep` covers a caller that changes a single
   * 表頭 column or one type's points in place instead of replacing the object,
   * so no edit can be persisted only by accident of how it was made.
   */
  watch(
    [paperSize, headerFields, typePoints],
    () => {
      const prefs: ExportPrefs = {
        paperSize: paperSize.value,
        headerFields: { ...headerFields.value },
        typePoints: { ...typePoints.value },
      }
      writeStoredValue(EXPORT_PREFS_STORAGE_KEY, prefs)
    },
    { deep: true },
  )

  return { paperSize, headerFields, typePoints }
})
