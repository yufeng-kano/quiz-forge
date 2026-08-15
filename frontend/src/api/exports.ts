/** Word export endpoints, see docs/export.md 選題流程. */

import { apiGet, apiPost } from './client'
import { API_BASE_PATH } from './config'
import type { ExportListItem, ExportRequest, ExportResult } from './types'

/**
 * `POST /api/v1/exports` — queues the `export_docx` job that validates the
 * selection and renders both documents. Nothing is rendered synchronously, so
 * the caller polls the returned job id for progress.
 */
export function createExportJob(request: ExportRequest): Promise<ExportResult> {
  return apiPost<ExportResult>('/exports', request)
}

/** `GET /api/v1/exports` — every past export, newest first. */
export function listExports(): Promise<ExportListItem[]> {
  return apiGet<ExportListItem[]>('/exports')
}

/**
 * Href of the 題目卷 file.
 *
 * The download endpoints are plain same-origin `FileResponse`s that already
 * carry a `Content-Disposition` filename, so a normal anchor downloads them
 * with the right name. Fetching them into a blob would only add a copy in
 * memory and lose that filename.
 */
export function questionsDocxUrl(exportId: number): string {
  return `${API_BASE_PATH}/exports/${encodeURIComponent(exportId)}/questions.docx`
}

/** Href of the 答案卷 file; same reasoning as `questionsDocxUrl`. */
export function answersDocxUrl(exportId: number): string {
  return `${API_BASE_PATH}/exports/${encodeURIComponent(exportId)}/answers.docx`
}
