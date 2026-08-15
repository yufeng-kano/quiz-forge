/** LLM usage endpoint. */

import { apiGet } from './client'
import type { UsageSummary } from './types'

/** `GET /api/v1/usage` — cumulative token usage grouped by model and by purpose. */
export function getUsage(): Promise<UsageSummary> {
  return apiGet<UsageSummary>('/usage')
}
