/** Dashboard overview counts, see docs/frontend.md 頁面清單 `/`. */

import { apiGet } from './client'
import type { Stats } from './types'

/** `GET /api/v1/stats` — documents/questions by status, chunk, category, failed-job and LLM totals. */
export function getStats(): Promise<Stats> {
  return apiGet<Stats>('/stats')
}
