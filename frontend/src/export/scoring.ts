/**
 * The arithmetic behind 配分設定 (docs/frontend.md 匯出頁).
 *
 * A question's score comes from one of two places: its own override, or the
 * default of its type — the override wins, exactly as the backend resolves
 * them (docs/export.md 配分參數). Nothing here touches the API or the DOM, so
 * the rule lives in one place and both the summary line on the page and the
 * running total inside the modal read the same number.
 */

import type { ExportPoints, ExportQuestionPoints, QuestionType } from '@/api'
import { isQuestionType } from '@/api'
import type { SelectedQuestionRow } from '@/composables/useSelectedQuestions'

/** A selected question reduced to what scoring needs. */
export interface ScoredQuestion {
  id: number
  /** `null` when the question could not be resolved or has an unknown type. */
  type: QuestionType | null
}

/** Per-question overrides while they are being edited, keyed by question id. */
export type QuestionPointsDraft = Record<number, number>

export function toScoredQuestions(rows: readonly SelectedQuestionRow[]): ScoredQuestion[] {
  return rows.map((row) => {
    const type = row.question?.type
    return { id: row.id, type: type !== undefined && isQuestionType(type) ? type : null }
  })
}

/**
 * A points field's value, or `null` when the field carries no usable score.
 *
 * Only positive whole numbers count: blank, zero and anything the field cannot
 * be read as are all "no score for this", which is what the backend's
 * "points value must be positive" rule leaves room for.
 */
export function parsePointsInput(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '' || !/^\d+$/.test(trimmed)) {
    return null
  }
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

/** The type default a question inherits when it has no override of its own. */
export function inheritedPoints(
  question: ScoredQuestion,
  typePoints: Readonly<ExportPoints>,
): number | null {
  return question.type === null ? null : (typePoints[question.type] ?? null)
}

/** What a question is actually worth, override first, then its type default. */
export function effectivePoints(
  question: ScoredQuestion,
  typePoints: Readonly<ExportPoints>,
  questionPoints: Readonly<QuestionPointsDraft>,
): number | null {
  return questionPoints[question.id] ?? inheritedPoints(question, typePoints)
}

/** Sum of every selected question's score; an unscored question adds nothing. */
export function totalPoints(
  questions: readonly ScoredQuestion[],
  typePoints: Readonly<ExportPoints>,
  questionPoints: Readonly<QuestionPointsDraft>,
): number {
  return questions.reduce(
    (total, question) => total + (effectivePoints(question, typePoints, questionPoints) ?? 0),
    0,
  )
}

/** How many of the selected questions carry a score. */
export function scoredCount(
  questions: readonly ScoredQuestion[],
  typePoints: Readonly<ExportPoints>,
  questionPoints: Readonly<QuestionPointsDraft>,
): number {
  return questions.filter(
    (question) => effectivePoints(question, typePoints, questionPoints) !== null,
  ).length
}

/**
 * Splits `target` points evenly over `count` questions.
 *
 * Integer division decides the share and the remainder is handed out one point
 * at a time to the questions at the front, so 100 over 3 becomes 34 / 33 / 33
 * and the shares always add back up to `target` exactly.
 *
 * The caller must keep `target` at least as large as `count`: below that some
 * share would be zero, which the backend rejects as a non-positive score.
 */
export function distributePoints(target: number, count: number): number[] {
  if (count <= 0) {
    return []
  }
  const base = Math.floor(target / count)
  const remainder = target - base * count
  return Array.from({ length: count }, (_unused, index) => (index < remainder ? base + 1 : base))
}

/**
 * The overrides restricted to the questions that are still selected.
 *
 * A key outside `question_ids` is a 422 (docs/export.md 配分參數), and a
 * question removed from the selection after being given a score would leave
 * exactly such a key behind, so the request is built from the selection rather
 * than from the draft.
 */
export function collectQuestionPoints(
  selectedIds: readonly number[],
  questionPoints: Readonly<QuestionPointsDraft>,
): ExportQuestionPoints | undefined {
  const collected: ExportQuestionPoints = {}
  for (const id of selectedIds) {
    const points = questionPoints[id]
    if (points !== undefined) {
      collected[String(id)] = points
    }
  }
  return Object.keys(collected).length === 0 ? undefined : collected
}

/** Drops draft overrides whose question is no longer selected. */
export function pruneQuestionPoints(
  selectedIds: readonly number[],
  questionPoints: Readonly<QuestionPointsDraft>,
): QuestionPointsDraft {
  const kept: QuestionPointsDraft = {}
  for (const id of selectedIds) {
    const points = questionPoints[id]
    if (points !== undefined) {
      kept[id] = points
    }
  }
  return kept
}

/**
 * The type defaults restricted to the types actually on the paper.
 *
 * The defaults are remembered across sessions, so they can name a type that
 * this selection does not contain; such an entry would print nothing and only
 * makes the request harder to read.
 */
export function collectTypePoints(
  types: readonly QuestionType[],
  typePoints: Readonly<ExportPoints>,
): ExportPoints | undefined {
  const collected: ExportPoints = {}
  for (const type of types) {
    const points = typePoints[type]
    if (points !== undefined) {
      collected[type] = points
    }
  }
  return Object.keys(collected).length === 0 ? undefined : collected
}
