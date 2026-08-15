/**
 * Generation jobs launched in this session (`/generate`).
 *
 * `POST /api/v1/generate` returns a job id and nothing else, and no endpoint
 * lists past generation jobs, so what was requested — type, count, difficulty,
 * how wide the scope was — is only knowable at submit time. It is kept here so
 * navigating away and back still shows the jobs that are running, with their
 * progress picked up again by `useJobPolling`.
 *
 * This is session state on purpose: it is not persisted, and it never pretends
 * to be a complete history of every job the backend ever ran.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { createGenerationJob, type GenerateRequest, type QuestionType } from '@/api'

export interface GenerationJobEntry {
  jobId: number
  questionType: QuestionType
  count: number
  difficulty: string | null
  documentCount: number
  categoryCount: number
  /** ISO timestamp of the submission, formatted for display by the view. */
  submittedAt: string
}

export const useGenerationStore = defineStore('generation', () => {
  /** Newest first. */
  const jobs = ref<GenerationJobEntry[]>([])

  async function submit(request: GenerateRequest): Promise<GenerationJobEntry> {
    const result = await createGenerationJob(request)
    const entry: GenerationJobEntry = {
      jobId: result.job_id,
      questionType: request.question_type,
      count: request.count,
      difficulty: request.difficulty ?? null,
      documentCount: request.document_ids?.length ?? 0,
      categoryCount: request.category_ids?.length ?? 0,
      submittedAt: new Date().toISOString(),
    }
    jobs.value = [entry, ...jobs.value]
    return entry
  }

  return { jobs, submit }
})
