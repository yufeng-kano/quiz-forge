/**
 * Response types for `/api/v1`.
 *
 * This is the single place the frontend describes the backend contract: when a
 * server schema changes, only this file is edited — callers (`src/api/*.ts`,
 * stores, views) never redeclare shapes of their own.
 */

/** `jobs.status`, see the background-task section of docs/architecture.md. */
export const JOB_STATUSES = ['pending', 'running', 'done', 'failed'] as const

export type JobStatus = (typeof JOB_STATUSES)[number]

/** Statuses that end a job, so polling can stop. */
export const TERMINAL_JOB_STATUSES = ['done', 'failed'] as const satisfies readonly JobStatus[]

export function isTerminalJobStatus(status: JobStatus): boolean {
  return TERMINAL_JOB_STATUSES.some((terminal) => terminal === status)
}

/**
 * `GET /api/v1/jobs/{id}` and `POST /api/v1/jobs/{id}/retry`.
 *
 * `progress` is free-form text (for example `12/40`), not a percentage. The
 * backend currently sends an empty string before a job starts; `null` is
 * allowed here so a future nullable column would not ripple into callers.
 */
export interface Job {
  id: number
  kind: string
  status: JobStatus
  progress: string | null
  error: string | null
  retry_count: number
  created_at: string
  updated_at: string
}

/**
 * `documents.source_type`. The backend types this field as a plain string but
 * a CHECK constraint restricts it to these two values, so the union is safe.
 */
export type DocumentSourceType = 'upload' | 'url'

/**
 * One row of `GET /api/v1/documents`.
 *
 * `status` is a plain string rather than a union: docs/data-model.md does not
 * define the value range of `documents.status`, and inventing one here would
 * be fake data. It can be narrowed once the pipeline settles.
 */
export interface DocumentListItem {
  id: number
  source_type: DocumentSourceType
  title: string
  status: string
  source_url: string | null
  created_at: string
  page_count: number
}

/** One `pages` row as exposed on the document detail response. */
export interface DocumentPage {
  id: number
  page_no: number
  status: string
  /** Parsed Markdown; figure placeholders already point at `/api/v1/assets/{id}`. */
  markdown: string | null
}

/** A node of the `categories` hierarchy. */
export interface Category {
  id: number
  name: string
  parent_id: number | null
}

/** One `chunks` row. The embedding vector itself is never sent to the client. */
export interface DocumentChunk {
  id: number
  content: string
  tags: string[]
  category: Category | null
  has_embedding: boolean
}

/** `GET /api/v1/documents/{id}` — the document with its pages and chunks. */
export interface DocumentDetail {
  id: number
  source_type: DocumentSourceType
  title: string
  status: string
  source_url: string | null
  summary: string | null
  created_at: string
  pages: DocumentPage[]
  chunks: DocumentChunk[]
}

/**
 * `POST /api/v1/documents/upload` and `POST /api/v1/documents/url`: both create
 * a document and queue the `parse_document` job whose id the caller then polls.
 */
export interface DocumentUploadResult {
  document: DocumentListItem
  job_id: number
}

/** Request body of `POST /api/v1/documents/url`. */
export interface DocumentUrlRequest {
  url: string
  title?: string
}

/** Numeric fields shared by every usage aggregate. */
export interface UsageTotals {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  call_count: number
}

export interface ModelUsage extends UsageTotals {
  model: string
}

export interface PurposeUsage extends UsageTotals {
  purpose: string
}

/** `GET /api/v1/usage`. */
export interface UsageSummary {
  total: UsageTotals
  by_model: ModelUsage[]
  by_purpose: PurposeUsage[]
}
