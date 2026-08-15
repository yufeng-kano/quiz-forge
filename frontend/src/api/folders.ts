/**
 * Library folder endpoints (docs/ingestion.md 文件管理).
 *
 * Folders only organise the document library; moving a document in or out of
 * one is a `PATCH /api/v1/documents/{id}` (see `patchDocument`), not a call
 * here. They have nothing to do with `/categories`, the LLM classification
 * that drives question-generation scope.
 */

import { apiDelete, apiGet, apiPatch, apiPost } from './client'
import type { Folder, FolderInput } from './types'

/** `GET /api/v1/folders` — every folder with its document count, ordered by id. */
export function listFolders(): Promise<Folder[]> {
  return apiGet<Folder[]>('/folders')
}

/** `POST /api/v1/folders` — a folder whose name is already taken is a 409. */
export function createFolder(input: FolderInput): Promise<Folder> {
  return apiPost<Folder>('/folders', input)
}

/** `PATCH /api/v1/folders/{id}` — rename; a name another folder holds is a 409. */
export function renameFolder(folderId: number, input: FolderInput): Promise<Folder> {
  return apiPatch<Folder>(`/folders/${encodeURIComponent(folderId)}`, input)
}

/**
 * `DELETE /api/v1/folders/{id}` — responds 204 with no body and is never
 * refused: the documents inside simply become 未分類 (`folder_id` is set to
 * null server-side), so the caller has to refresh the document list afterwards.
 */
export function deleteFolder(folderId: number): Promise<void> {
  return apiDelete(`/folders/${encodeURIComponent(folderId)}`)
}
