/** Background-task endpoints, see the background-task section of docs/architecture.md. */

import { apiGet, apiPost } from './client'
import type { QueryParams } from './client'
import type { Job, JobListQuery } from './types'

/**
 * `GET /api/v1/jobs` — newest first, optionally filtered by status and kind.
 *
 * An omitted parameter is left out of the query string entirely; without
 * `limit` the backend applies `Settings.jobs_list_limit_default`.
 */
export function listJobs(query: JobListQuery = {}): Promise<Job[]> {
  const params: QueryParams = {
    status: query.status,
    kind: query.kind,
    limit: query.limit,
  }
  return apiGet<Job[]>('/jobs', params)
}

/** `GET /api/v1/jobs/{id}` — status / progress / error, used for polling. */
export function getJob(jobId: number): Promise<Job> {
  return apiGet<Job>(`/jobs/${encodeURIComponent(jobId)}`)
}

/** `POST /api/v1/jobs/{id}/retry` — put a `failed` job back to `pending`. */
export function retryJob(jobId: number): Promise<Job> {
  return apiPost<Job>(`/jobs/${encodeURIComponent(jobId)}/retry`)
}
