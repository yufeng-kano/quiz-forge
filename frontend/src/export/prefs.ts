/**
 * Shape and parsing of the 匯出 preferences kept in `localStorage`.
 *
 * What survives a browser restart is the setup of the form, not the work in
 * progress: the paper size, which 表頭 columns are printed, and the default
 * points of each question type (docs/frontend.md 匯出頁). The question
 * selection and the per-question overrides stay in the session — they belong to
 * one particular paper, not to how this teacher always builds papers.
 *
 * The stored value comes from an earlier run of a possibly older build, so it
 * is never trusted: every field is checked on its own and an unusable one falls
 * back to its default while the rest is still honoured.
 */

import {
  DEFAULT_PAPER_SIZE,
  EXPORT_HEADER_FIELD_NAMES,
  findPaperSize,
  isQuestionType,
  type ExportHeaderFields,
  type ExportPoints,
  type PaperSize,
} from '@/api'

/**
 * Namespaced and versioned storage key. A change to the shape below that older
 * values cannot be read into gets a new `v…` suffix instead of a migration.
 */
export const EXPORT_PREFS_STORAGE_KEY = 'quiz-forge:export-prefs:v1'

export interface ExportPrefs {
  paperSize: PaperSize
  headerFields: ExportHeaderFields
  /** Default points per question type; a type absent from it carries no marks. */
  typePoints: ExportPoints
}

/**
 * Every 表頭 column ticked, which is also the server-side default. Written out
 * rather than built in a loop so that adding a field to
 * `EXPORT_HEADER_FIELD_NAMES` fails to compile here until it is given a
 * default.
 */
export function defaultHeaderFields(): ExportHeaderFields {
  return { class: true, seat: true, name: true, score: true }
}

/** A fresh set of defaults; callers mutate their copy, so it is never shared. */
export function defaultExportPrefs(): ExportPrefs {
  return {
    paperSize: DEFAULT_PAPER_SIZE,
    headerFields: defaultHeaderFields(),
    typePoints: {},
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parsePaperSize(value: unknown): PaperSize | null {
  return typeof value === 'string' ? (findPaperSize(value)?.name ?? null) : null
}

function parseHeaderFields(value: unknown): ExportHeaderFields {
  const fields = defaultHeaderFields()
  if (!isRecord(value)) {
    return fields
  }
  for (const name of EXPORT_HEADER_FIELD_NAMES) {
    const stored = value[name]
    if (typeof stored === 'boolean') {
      fields[name] = stored
    }
  }
  return fields
}

function parseTypePoints(value: unknown): ExportPoints {
  const points: ExportPoints = {}
  if (!isRecord(value)) {
    return points
  }
  for (const [type, stored] of Object.entries(value)) {
    // A type this build no longer knows, or a score the backend would reject
    // as non-positive, is dropped rather than carried into a request.
    if (
      isQuestionType(type) &&
      typeof stored === 'number' &&
      Number.isInteger(stored) &&
      stored > 0
    ) {
      points[type] = stored
    }
  }
  return points
}

/** Reads whatever was stored into a usable `ExportPrefs`, never throwing. */
export function parseExportPrefs(value: unknown): ExportPrefs {
  const defaults = defaultExportPrefs()
  if (!isRecord(value)) {
    return defaults
  }
  return {
    paperSize: parsePaperSize(value['paperSize']) ?? defaults.paperSize,
    headerFields: parseHeaderFields(value['headerFields']),
    typePoints: parseTypePoints(value['typePoints']),
  }
}
