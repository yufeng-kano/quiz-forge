/**
 * Shape and parsing of the 匯出 preferences kept in `localStorage`.
 *
 * What survives a browser restart is the setup of the form, not the work in
 * progress: the paper size, which 表頭 columns are printed, the target total
 * and each question type's share of it in percent
 * (docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md D33).
 * The question selection and the per-question points stay in the session —
 * they belong to one particular paper, not to how this teacher always builds
 * papers.
 *
 * The stored value comes from an earlier run of a possibly older build, so it
 * is never trusted: every field is checked on its own and an unusable one falls
 * back to its default while the rest is still honoured. The pre-D33
 * `typePoints` key is simply ignored by this parser — same storage key, no
 * migration needed.
 */

import {
  DEFAULT_PAPER_SIZE,
  EXPORT_HEADER_FIELD_NAMES,
  findPaperSize,
  isQuestionType,
  type ExportHeaderFields,
  type PaperSize,
  type QuestionType,
} from '@/api'

/**
 * Namespaced and versioned storage key. A change to the shape below that older
 * values cannot be read into gets a new `v…` suffix instead of a migration.
 */
export const EXPORT_PREFS_STORAGE_KEY = 'quiz-forge:export-prefs:v1'

/** Each question type's share of the target total, in whole percent (1–100). */
export type ExportTypePercents = Partial<Record<QuestionType, number>>

/** The 依比例分配 tool's default target when nothing was stored yet. */
export const DEFAULT_TARGET_TOTAL = 100

export interface ExportPrefs {
  paperSize: PaperSize
  headerFields: ExportHeaderFields
  /** 依比例分配／全部平均 target total, a positive integer. */
  targetTotal: number
  /** A type absent from it has no percentage set. */
  typePercents: ExportTypePercents
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
    targetTotal: DEFAULT_TARGET_TOTAL,
    typePercents: {},
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

function parseTargetTotal(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null
}

function parseTypePercents(value: unknown): ExportTypePercents {
  const percents: ExportTypePercents = {}
  if (!isRecord(value)) {
    return percents
  }
  for (const [type, stored] of Object.entries(value)) {
    // A type this build no longer knows, or a share outside 1–100, is dropped
    // rather than fed into the distribution tool.
    if (
      isQuestionType(type) &&
      typeof stored === 'number' &&
      Number.isInteger(stored) &&
      stored > 0 &&
      stored <= 100
    ) {
      percents[type] = stored
    }
  }
  return percents
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
    targetTotal: parseTargetTotal(value['targetTotal']) ?? defaults.targetTotal,
    typePercents: parseTypePercents(value['typePercents']),
  }
}
