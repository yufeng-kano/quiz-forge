/** Background-task endpoints, see the background-task section of docs/architecture.md. */

import { apiGet, apiPost } from './client'
import type { Job } from './types'

/** `GET /api/v1/jobs/{id}` — status / progress / error, used for polling. */
export function getJob(jobId: number): Promise<Job> {
  return apiGet<Job>(`/jobs/${encodeURIComponent(jobId)}`)
}

/** `POST /api/v1/jobs/{id}/retry` — put a `failed` job back to `pending`. */
export function retryJob(jobId: number): Promise<Job> {
  return apiPost<Job>(`/jobs/${encodeURIComponent(jobId)}/retry`)
}
