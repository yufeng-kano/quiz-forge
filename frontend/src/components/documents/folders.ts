/**
 * Plumbing shared by the 文件庫 folder column, its rows and its pickers:
 * what "which folder is being shown" means, and how a dragged document row
 * travels to a folder through the drag-and-drop `DataTransfer`.
 *
 * Kept out of the components so the sidebar, the table and the 移至資料夾
 * modal all agree on one representation instead of each inventing its own
 * (same reason as `components/generate/scope.ts`).
 */

import type { DocumentListItem } from '@/api'

/**
 * A move destination: a folder id, or `null` for 未分類 — exactly the value
 * `PATCH /api/v1/documents/{id}` takes as `folder_id`.
 */
export type FolderTarget = number | null

/** What the folder column is currently filtering the library by. */
export type FolderFilter = 'all' | 'unfiled' | number

/** Whether a document belongs in the list under the given filter. */
export function matchesFolderFilter(document: DocumentListItem, filter: FolderFilter): boolean {
  if (filter === 'all') {
    return true
  }
  if (filter === 'unfiled') {
    return document.folder_id === null
  }
  return document.folder_id === filter
}

/**
 * Custom MIME type carrying the dragged document id.
 *
 * A private type is what makes a drop target able to tell "a row of this
 * table" from any other draggable thing the browser may hand it (a file, a
 * selection, the source link inside the very row being dragged). Only this
 * type is inspected, and `dragover` can read `types` even though it may not
 * read the data itself, which is what the drag-over highlight keys on.
 */
export const DOCUMENT_DRAG_MIME = 'application/x-quizforge-document-id'

/** Attach the dragged document's id to the drag. */
export function setDocumentDragPayload(dataTransfer: DataTransfer, documentId: number): void {
  dataTransfer.effectAllowed = 'move'
  dataTransfer.setData(DOCUMENT_DRAG_MIME, String(documentId))
}

/** Whether this drag is one of our document rows (readable during `dragover`). */
export function hasDocumentDragPayload(dataTransfer: DataTransfer | null): boolean {
  return dataTransfer !== null && Array.from(dataTransfer.types).includes(DOCUMENT_DRAG_MIME)
}

/**
 * The dragged document id, or `null` when the drop carries anything else — a
 * foreign drag, an empty payload or text that is not a positive integer. The
 * caller ignores a `null` rather than guessing an id.
 */
export function readDocumentDragPayload(dataTransfer: DataTransfer | null): number | null {
  if (dataTransfer === null) {
    return null
  }
  const raw = dataTransfer.getData(DOCUMENT_DRAG_MIME)
  if (raw === '') {
    return null
  }
  const documentId = Number(raw)
  return Number.isInteger(documentId) && documentId > 0 ? documentId : null
}
