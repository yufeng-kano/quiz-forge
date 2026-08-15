/** Question generation endpoint, see docs/question-bank.md 出題流程. */

import { apiPost } from './client'
import type { GenerateRequest, GenerateResult } from './types'

/**
 * `POST /api/v1/generate` — queues a `generate_questions` job and returns its
 * id. Nothing is generated synchronously: the caller polls
 * `GET /api/v1/jobs/{id}` for progress.
 */
export function createGenerationJob(request: GenerateRequest): Promise<GenerateResult> {
  return apiPost<GenerateResult>('/generate', request)
}
