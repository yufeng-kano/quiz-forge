/**
 * Reads a `questions.payload` JSON object into the typed shape its `type`
 * promises (docs/question-bank.md payload schema).
 *
 * `GET /api/v1/questions` types the column as a free-form object, so the
 * frontend checks the shape itself instead of assuming it: the rendering and
 * editing components then work on concrete fields with no casts. A payload
 * that does not match its type yields `null`, which the card turns into a
 * visible notice — never a blank card or a crashed list.
 *
 * Every value is copied into a fresh object or array while being checked, so
 * the result can be edited as a draft without touching the stored item.
 */

import {
  isQuestionType,
  type AnalogyPayload,
  type ComparisonDifference,
  type ComparisonModelAnswer,
  type ComparisonPayload,
  type FillBlankPayload,
  type QuestionListItem,
  type ShortAnswerPayload,
  type SingleChoicePayload,
  type TrueFalsePayload,
  type TypedQuestionPayload,
} from '@/api'

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readString(source: UnknownRecord, key: string): string | null {
  const value = source[key]
  return typeof value === 'string' ? value : null
}

function readBoolean(source: UnknownRecord, key: string): boolean | null {
  const value = source[key]
  return typeof value === 'boolean' ? value : null
}

function readInteger(source: UnknownRecord, key: string): number | null {
  const value = source[key]
  return typeof value === 'number' && Number.isInteger(value) ? value : null
}

function readStringArray(source: UnknownRecord, key: string): string[] | null {
  const value = source[key]
  if (!Array.isArray(value)) {
    return null
  }
  const items: string[] = []
  for (const item of value) {
    if (typeof item !== 'string') {
      return null
    }
    items.push(item)
  }
  return items
}

/** `null` and a missing key both mean "no explanation", not a broken payload. */
function readOptionalString(source: UnknownRecord, key: string): string | null {
  const value = source[key]
  return typeof value === 'string' ? value : null
}

function readComparisonModelAnswer(source: UnknownRecord): ComparisonModelAnswer | null {
  const raw = source['model_answer']
  if (!isRecord(raw)) {
    return null
  }
  const similarities = readStringArray(raw, 'similarities')
  if (similarities === null) {
    return null
  }
  const rawDifferences = raw['differences']
  if (!Array.isArray(rawDifferences)) {
    return null
  }
  const differences: ComparisonDifference[] = []
  for (const item of rawDifferences) {
    if (!isRecord(item)) {
      return null
    }
    const aspect = readString(item, 'aspect')
    const a = readString(item, 'a')
    const b = readString(item, 'b')
    if (aspect === null || a === null || b === null) {
      return null
    }
    differences.push({ aspect, a, b })
  }
  return { similarities, differences }
}

function parseComparison(payload: UnknownRecord): ComparisonPayload | null {
  const stem = readString(payload, 'stem')
  const subjectA = readString(payload, 'subject_a')
  const subjectB = readString(payload, 'subject_b')
  const aspects = readStringArray(payload, 'aspects')
  const modelAnswer = readComparisonModelAnswer(payload)
  if (
    stem === null ||
    subjectA === null ||
    subjectB === null ||
    aspects === null ||
    modelAnswer === null
  ) {
    return null
  }
  return {
    stem,
    subject_a: subjectA,
    subject_b: subjectB,
    aspects,
    model_answer: modelAnswer,
  }
}

function parseAnalogy(payload: UnknownRecord): AnalogyPayload | null {
  const a = readString(payload, 'a')
  const b = readString(payload, 'b')
  const c = readString(payload, 'c')
  const answer = readString(payload, 'answer')
  if (a === null || b === null || c === null || answer === null) {
    return null
  }
  const rawOptions = payload['options']
  let options: string[] | null = null
  if (rawOptions !== null && rawOptions !== undefined) {
    options = readStringArray(payload, 'options')
    if (options === null) {
      return null
    }
  }
  return { a, b, c, answer, options, explanation: readOptionalString(payload, 'explanation') }
}

function parseSingleChoice(payload: UnknownRecord): SingleChoicePayload | null {
  const stem = readString(payload, 'stem')
  const options = readStringArray(payload, 'options')
  const answerIndex = readInteger(payload, 'answer_index')
  if (stem === null || options === null || answerIndex === null) {
    return null
  }
  return {
    stem,
    options,
    answer_index: answerIndex,
    explanation: readOptionalString(payload, 'explanation'),
  }
}

function parseTrueFalse(payload: UnknownRecord): TrueFalsePayload | null {
  const stem = readString(payload, 'stem')
  const answer = readBoolean(payload, 'answer')
  if (stem === null || answer === null) {
    return null
  }
  return { stem, answer, explanation: readOptionalString(payload, 'explanation') }
}

function parseFillBlank(payload: UnknownRecord): FillBlankPayload | null {
  const stem = readString(payload, 'stem')
  const answers = readStringArray(payload, 'answers')
  if (stem === null || answers === null) {
    return null
  }
  return { stem, answers }
}

function parseShortAnswer(payload: UnknownRecord): ShortAnswerPayload | null {
  const stem = readString(payload, 'stem')
  const modelAnswer = readString(payload, 'model_answer')
  const keyPoints = readStringArray(payload, 'key_points')
  if (stem === null || modelAnswer === null || keyPoints === null) {
    return null
  }
  return { stem, model_answer: modelAnswer, key_points: keyPoints }
}

/** The blank marker of a `fill_blank` stem; `answers` must match its count. */
export const FILL_BLANK_MARKER = '____'

export function countFillBlankMarkers(stem: string): number {
  return stem.split(FILL_BLANK_MARKER).length - 1
}

/**
 * Pair a question's `type` with its checked payload, or `null` when the type
 * is unknown or the payload does not match it.
 */
export function toTypedPayload(question: QuestionListItem): TypedQuestionPayload | null {
  if (!isQuestionType(question.type)) {
    return null
  }
  const raw = question.payload
  switch (question.type) {
    case 'comparison': {
      const payload = parseComparison(raw)
      return payload === null ? null : { type: 'comparison', payload }
    }
    case 'analogy': {
      const payload = parseAnalogy(raw)
      return payload === null ? null : { type: 'analogy', payload }
    }
    case 'single_choice': {
      const payload = parseSingleChoice(raw)
      return payload === null ? null : { type: 'single_choice', payload }
    }
    case 'true_false': {
      const payload = parseTrueFalse(raw)
      return payload === null ? null : { type: 'true_false', payload }
    }
    case 'fill_blank': {
      const payload = parseFillBlank(raw)
      return payload === null ? null : { type: 'fill_blank', payload }
    }
    case 'short_answer': {
      const payload = parseShortAnswer(raw)
      return payload === null ? null : { type: 'short_answer', payload }
    }
  }
}
