/** Document ingestion and per-page retry endpoints, see docs/ingestion.md. */

import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from './client'
import type {
  DocumentDetail,
  DocumentListItem,
  DocumentPatch,
  DocumentUploadResult,
  Job,
  RechunkResult,
} from './types'

/**
 * `GET /api/v1/documents` — newest first, every document regardless of folder.
 *
 * The endpoint also accepts `folder_id` / `unfiled`, but the frontend does not
 * use them: this is a single-user library the app already loads in full (the
 * 上傳 tab, the 出題 picker and the folder counts all need the whole list), so
 * the 文件庫 folder filter narrows what is in memory instead of refetching.
 */
export function listDocuments(): Promise<DocumentListItem[]> {
  return apiGet<DocumentListItem[]>('/documents')
}

/**
 * `PATCH /api/v1/documents/{id}` — rename and/or move (docs/ingestion.md 文件
 * 管理). Only the fields present in `patch` are changed; `folder_id: null`
 * unfiles the document and an unknown folder id comes back as 404. The
 * response is the same full detail shape as `GET /api/v1/documents/{id}`.
 */
export function patchDocument(documentId: number, patch: DocumentPatch): Promise<DocumentDetail> {
  return apiPatch<DocumentDetail>(`/documents/${encodeURIComponent(documentId)}`, patch)
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

/**
 * `POST /api/v1/documents/{id}/rechunk` — rebuild every chunk of the document
 * from the page Markdown that is already parsed. The whole chunk stage runs
 * again (splitting, LLM classification, embedding), so it costs API calls; the
 * caller must confirm with the user first. A document with no `ready` page
 * comes back as 409.
 */
export function rechunkDocument(documentId: number): Promise<RechunkResult> {
  return apiPost<RechunkResult>(`/documents/${encodeURIComponent(documentId)}/rechunk`)
}

/** `POST /api/v1/pages/{id}/retry` — retry a single page, never the whole document. */
export function retryPage(pageId: number): Promise<Job> {
  return apiPost<Job>(`/pages/${encodeURIComponent(pageId)}/retry`)
}
