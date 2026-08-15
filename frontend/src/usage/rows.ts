/**
 * Turns `GET /api/v1/usage` aggregates into table rows.
 *
 * Both groupings carry the same four numbers and differ only in what their
 * first column names, so one row shape feeds one table component. The backend
 * groups without an `ORDER BY`, so the order is decided here: heaviest total
 * first, which is what the user is looking for when checking spend.
 */

import type { UsageSummary, UsageTotals } from '@/api'
import { purposeLabel } from './labels'

export interface UsageTableRow extends UsageTotals {
  /** Stable list key: the model name or the raw purpose string. */
  key: string
  /** What the first column shows. */
  label: string
}

function byTotalTokensDesc(a: UsageTableRow, b: UsageTableRow): number {
  return b.total_tokens - a.total_tokens || a.label.localeCompare(b.label)
}

export function modelRows(summary: UsageSummary): UsageTableRow[] {
  return summary.by_model
    .map((row) => ({
      key: row.model,
      label: row.model,
      prompt_tokens: row.prompt_tokens,
      completion_tokens: row.completion_tokens,
      total_tokens: row.total_tokens,
      call_count: row.call_count,
    }))
    .sort(byTotalTokensDesc)
}

export function purposeRows(summary: UsageSummary): UsageTableRow[] {
  return summary.by_purpose
    .map((row) => ({
      key: row.purpose,
      label: purposeLabel(row.purpose),
      prompt_tokens: row.prompt_tokens,
      completion_tokens: row.completion_tokens,
      total_tokens: row.total_tokens,
      call_count: row.call_count,
    }))
    .sort(byTotalTokensDesc)
}
