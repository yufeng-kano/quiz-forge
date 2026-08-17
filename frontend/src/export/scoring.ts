/**
 * The arithmetic behind 題目與配分 (docs/frontend.md 匯出頁).
 *
 * Since docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md
 * D33 a paper's scoring is exactly the per-question map in `exportSelection`:
 * the type-level control is a *tool* (each type's share of the target total in
 * percent, split evenly inside the type) that writes that map, not a second
 * layer the backend has to resolve. Nothing here touches the API or the DOM,
 * so the rules live in one place and the summary line on the page and the
 * running total inside the modal read the same numbers.
 */

import type { ExportQuestionPoints } from '@/api'

/**
 * A numeric field's value, or `null` when the field carries no usable score.
 *
 * Accepts `string | number` because Vue's `v-model` on an
 * `<input type="number">` auto-casts to `number` (D34 — the `.trim()` crash);
 * everything is normalised to text before validation. Only positive whole
 * numbers count: blank, zero and anything unreadable are all "no score for
 * this", which is what the backend's "points value must be positive" rule
 * leaves room for.
 */
export function parsePointsInput(raw: string | number): number | null {
  const trimmed = String(raw).trim()
  if (trimmed === '' || !/^\d+$/.test(trimmed)) {
    return null
  }
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

/** A percentage field's value: a whole number of percent in 1–100, or `null`. */
export function parsePercentInput(raw: string | number): number | null {
  const parsed = parsePointsInput(raw)
  return parsed !== null && parsed <= 100 ? parsed : null
}

/** Sum of every selected question's score; an unscored question adds nothing. */
export function totalPoints(
  questionIds: readonly number[],
  questionPoints: Readonly<Record<number, number>>,
): number {
  return questionIds.reduce((total, id) => total + (questionPoints[id] ?? 0), 0)
}

/** How many of the selected questions carry a score. */
export function scoredCount(
  questionIds: readonly number[],
  questionPoints: Readonly<Record<number, number>>,
): number {
  return questionIds.filter((id) => questionPoints[id] !== undefined).length
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
 * Splits `target` into one integer share per percentage, by largest remainder:
 * every share starts at the floor of its exact value and the leftover points go
 * one at a time to the largest fractional parts (ties to the earlier entry).
 *
 * When the percents sum to 100 the shares sum to `target` exactly. The caller
 * validates that; this function just never invents or drops a point relative
 * to `round(target × Σpercent / 100)`.
 */
export function percentShares(target: number, percents: readonly number[]): number[] {
  const exact = percents.map((percent) => (target * percent) / 100)
  const shares = exact.map(Math.floor)
  let leftover =
    Math.round(exact.reduce((sum, value) => sum + value, 0)) -
    shares.reduce((sum, value) => sum + value, 0)
  const order = exact
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index)
  for (const { index } of order) {
    if (leftover <= 0) {
      break
    }
    shares[index] = (shares[index] ?? 0) + 1
    leftover -= 1
  }
  return shares
}

/**
 * The overrides restricted to the questions that are still selected.
 *
 * A key outside `question_ids` is a 422 (docs/export.md 配分參數); the store
 * already prunes on deselect, but the request is still built from the
 * selection so no ordering of events can leave a stray key.
 */
export function collectQuestionPoints(
  selectedIds: readonly number[],
  questionPoints: Readonly<Record<number, number>>,
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
