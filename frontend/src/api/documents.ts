/** Document ingestion and per-page retry endpoints, see docs/ingestion.md. */

import { apiDelete, apiGet, apiPost, apiUpload } from './client'
import type { DocumentDetail, DocumentListItem, DocumentUploadResult, Job } from './types'

/** `GET /api/v1/documents` — newest first. */
export function listDocuments(): Promise<DocumentListItem[]> {
  return apiGet<DocumentListItem[]>('/documents')
}

/** `GET /api/v1/documents/{id}` — document with its pages and chunks. */
export function getDocument(documentId: number): Promise<DocumentDetail> {
  return apiGet<DocumentDetail>(`/documents/${encodeURIComponent(documentId)}`)
}

/** `DELETE /api/v1/documents/{id}` — responds 204 with no body. */
export function deleteDocument(documentId: number): Promise<void> {
  return apiDelete(`/documents/${encodeURIComponent(documentId)}`)
}

/**
 * `POST /api/v1/documents/upload` — multipart upload of a scan, PDF, Word file
 * or image. The endpoint takes the file only and derives the title from its
 * filename, so there is no title argument here.
 */
export function uploadDocument(file: File): Promise<DocumentUploadResult> {
  const form = new FormData()
  form.append('file', file)
  return apiUpload<DocumentUploadResult>('/documents/upload', form)
}

/** `POST /api/v1/documents/url` — import a web page; the URL is the default title. */
export function importDocumentFromUrl(url: string, title?: string): Promise<DocumentUploadResult> {
  return apiPost<DocumentUploadResult>('/documents/url', { url, title })
}

/** `POST /api/v1/pages/{id}/retry` — retry a single page, never the whole document. */
export function retryPage(pageId: number): Promise<Job> {
  return apiPost<Job>(`/pages/${encodeURIComponent(pageId)}/retry`)
}
