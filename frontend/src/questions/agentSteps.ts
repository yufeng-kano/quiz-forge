/**
 * Reads `conversation_messages.steps` into the shapes the 查詢過程 block
 * renders (docs/decisions/2026-08-17-bank-agent-semantic-selection.md D6).
 *
 * The backend declares the column as a free-form `list[object]`
 * (`backend.schemas.conversation.ConversationMessageOut`) and writes one entry
 * per step of the bounded loop (`backend.questions.agent.bank_agent_turn`):
 * a `search` entry with the filters it ran and how many questions matched, a
 * `propose` entry with the ids it chose, or a terminal `reply` entry.
 *
 * Nothing here trusts that shape blindly — the same reasoning as
 * `src/questions/payload.ts`: the log may have been written by an older build,
 * so every field is checked and an entry that cannot be read is dropped rather
 * than rendered as a broken row. A dropped entry costs one line of a
 * transparency log; a thrown error would cost the whole conversation.
 */

import { isQuestionType, type QuestionType } from '@/api'

/**
 * The filters of one `action="search"` step, in the same field set
 * `GET /api/v1/questions` takes (minus `status`, which the agent never
 * controls). A field the agent left out is `null`, i.e. "not narrowed".
 */
export interface BankAgentSearchFilters {
  similarTo: string | null
  q: string | null
  type: QuestionType | null
  difficulty: string | null
  categoryId: number | null
  limit: number | null
}

export interface BankAgentSearchStep {
  step: number
  action: 'search'
  filters: BankAgentSearchFilters
  /** Total matches before the per-step cap, i.e. what 命中 N 題 reports. */
  hitCount: number
}

export interface BankAgentProposeStep {
  step: number
  action: 'propose'
  /** What the model asked for; ids it could not propose were dropped later. */
  questionIds: number[]
}

export interface BankAgentReplyStep {
  step: number
  action: 'reply'
}

export type BankAgentStep = BankAgentSearchStep | BankAgentProposeStep | BankAgentReplyStep

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readInteger(source: UnknownRecord, key: string): number | null {
  const value = source[key]
  return typeof value === 'number' && Number.isInteger(value) ? value : null
}

/** A blank string is the same as an absent filter and must not render as one. */
function readNonEmptyString(source: UnknownRecord, key: string): string | null {
  const value = source[key]
  if (typeof value !== 'string') {
    return null
  }
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function readIntegerArray(source: UnknownRecord, key: string): number[] {
  const value = source[key]
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is number => typeof item === 'number' && Number.isInteger(item))
}

function readFilters(source: UnknownRecord): BankAgentSearchFilters {
  const raw = source['filters']
  if (!isRecord(raw)) {
    return { similarTo: null, q: null, type: null, difficulty: null, categoryId: null, limit: null }
  }
  const type = readNonEmptyString(raw, 'type')
  return {
    similarTo: readNonEmptyString(raw, 'similar_to'),
    q: readNonEmptyString(raw, 'q'),
    type: type !== null && isQuestionType(type) ? type : null,
    difficulty: readNonEmptyString(raw, 'difficulty'),
    categoryId: readInteger(raw, 'category_id'),
    limit: readInteger(raw, 'limit'),
  }
}

/** True when the step narrowed on nothing at all, i.e. it listed the bank. */
export function isEmptySearchFilters(filters: BankAgentSearchFilters): boolean {
  return (
    filters.similarTo === null &&
    filters.q === null &&
    filters.type === null &&
    filters.difficulty === null &&
    filters.categoryId === null
  )
}

function parseStep(entry: unknown): BankAgentStep | null {
  if (!isRecord(entry)) {
    return null
  }
  const step = readInteger(entry, 'step')
  const action = entry['action']
  if (step === null || typeof action !== 'string') {
    return null
  }
  if (action === 'search') {
    return {
      step,
      action: 'search',
      filters: readFilters(entry),
      hitCount: readInteger(entry, 'hit_count') ?? 0,
    }
  }
  if (action === 'propose') {
    return { step, action: 'propose', questionIds: readIntegerArray(entry, 'question_ids') }
  }
  if (action === 'reply') {
    return { step, action: 'reply' }
  }
  return null
}

/** Every readable entry of the log, in the order the turn ran them. */
export function parseAgentSteps(steps: readonly unknown[] | null): BankAgentStep[] {
  if (steps === null) {
    return []
  }
  const parsed: BankAgentStep[] = []
  for (const entry of steps) {
    const step = parseStep(entry)
    if (step !== null) {
      parsed.push(step)
    }
  }
  return parsed
}
