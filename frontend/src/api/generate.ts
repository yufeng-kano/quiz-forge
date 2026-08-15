/** Question generation endpoint, see docs/question-bank.md 出題流程. */

import { apiPost } from './client'
import type { GenerateRequest, GenerateResult } from './types'

/**
 * `POST /api/v1/generate` — queues one `generate_questions` job for the whole
 * `items` combination and returns its id. Nothing is generated synchronously:
 * the caller polls `GET /api/v1/jobs/{id}` for progress, which counts every
 * question of every item together.
 */
export function createGenerationJob(request: GenerateRequest): Promise<GenerateResult> {
  return apiPost<GenerateResult>('/generate', request)
}
