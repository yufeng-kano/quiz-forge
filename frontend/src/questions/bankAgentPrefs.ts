/**
 * localStorage preferences for the 題庫選題助手 column
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D10).
 *
 * Collapse state and the last open conversation are a convenience: a missing,
 * unreadable or outdated value falls back to "open on a wide viewport, closed
 * on a narrow one" and no conversation. The stored shape is never trusted.
 */

import { readStoredValue, writeStoredValue } from '@/utils/storage'

/**
 * Namespaced and versioned storage key. A change to the shape below that older
 * values cannot be read into gets a new `v…` suffix instead of a migration.
 */
export const BANK_AGENT_PREFS_KEY = 'quiz-forge:bank-agent-prefs:v1'

/** Same breakpoint the sidebar uses to collapse to icons. */
export const BANK_AGENT_WIDE_MIN_WIDTH_PX = 1080

export interface BankAgentPrefs {
  agentOpen: boolean
  activeConversationId: number | null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** True when the window is wide enough that the column should start open. */
export function defaultAgentOpen(): boolean {
  if (typeof window === 'undefined') {
    return true
  }
  return window.matchMedia(`(min-width: ${BANK_AGENT_WIDE_MIN_WIDTH_PX}px)`).matches
}

function parseAgentOpen(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function parseConversationId(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
    return null
  }
  return value
}

/** Reads whatever was stored into a usable prefs object, never throwing. */
export function readBankAgentPrefs(): BankAgentPrefs {
  const raw = readStoredValue(BANK_AGENT_PREFS_KEY)
  if (!isRecord(raw)) {
    return { agentOpen: defaultAgentOpen(), activeConversationId: null }
  }
  return {
    agentOpen: parseAgentOpen(raw['agentOpen']) ?? defaultAgentOpen(),
    activeConversationId: parseConversationId(raw['activeConversationId']),
  }
}

/** Stores the current column prefs; a refused store is silently left alone. */
export function writeBankAgentPrefs(prefs: BankAgentPrefs): void {
  writeStoredValue(BANK_AGENT_PREFS_KEY, prefs)
}
