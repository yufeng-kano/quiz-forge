/**
 * Document list state shared by `/` and `/documents/:id`.
 *
 * It lives in Pinia (docs/frontend.md: cross-page state belongs in a store)
 * because two things must survive navigation:
 * - the list itself, so returning from a detail page does not blank out;
 * - `parseJobIds`, the only place a `parse_document` job id is ever known.
 *   `GET /api/v1/documents` does not carry a job id and there is no endpoint
 *   that lists jobs, so the id from the upload/import response is remembered
 *   here; the detail page reuses it instead of polling blind.
 *
 * Read failures are stored (`loadError`) because the list renders around them;
 * the mutating actions throw instead, so the component that triggered one can
 * show the message next to its own control.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  deleteDocument,
  getDocument,
  importDocumentFromUrl,
  isActiveEntityStatus,
  listDocuments,
  patchDocument,
  uploadDocument,
  type DocumentDetail,
  type DocumentListItem,
  type DocumentUploadResult,
} from '@/api'
import { translateApiError } from '@/i18n/errors'

/** The detail response is a superset of a list row, apart from the page count. */
function toListItem(detail: DocumentDetail): DocumentListItem {
  return {
    id: detail.id,
    source_type: detail.source_type,
    title: detail.title,
    status: detail.status,
    source_url: detail.source_url,
    folder_id: detail.folder_id,
    created_at: detail.created_at,
    page_count: detail.pages.length,
  }
}

export const useDocumentsStore = defineStore('documents', () => {
  const documents = ref<DocumentListItem[]>([])
  /** True only while the first visible load runs; background refreshes are silent. */
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const loaded = ref(false)
  /** Latest `parse_document` job id per document id, from upload/import. */
  const parseJobIds = ref<Record<number, number>>({})

  /**
   * Rows the list has to poll itself: still working, and with no job id whose
   * polling would already refresh them (a document left `processing` by an
   * earlier session, for instance).
   */
  const hasUntrackedActiveDocument = computed(() =>
    documents.value.some(
      (item) => isActiveEntityStatus(item.status) && parseJobIds.value[item.id] === undefined,
    ),
  )

  async function load(options: { silent?: boolean } = {}): Promise<void> {
    const silent = options.silent ?? false
    if (!silent) {
      loading.value = true
    }
    try {
      documents.value = await listDocuments()
      loaded.value = true
      loadError.value = null
    } catch (error) {
      loadError.value = translateApiError(error)
    } finally {
      if (!silent) {
        loading.value = false
      }
    }
  }

  /** Load once per session; later visits reuse what is already in the store. */
  async function ensureLoaded(): Promise<void> {
    if (loaded.value) {
      return
    }
    await load()
  }

  function replaceRow(item: DocumentListItem): void {
    const index = documents.value.findIndex((existing) => existing.id === item.id)
    if (index === -1) {
      documents.value = [item, ...documents.value]
      return
    }
    documents.value.splice(index, 1, item)
  }

  /** Refresh a single row from `GET /api/v1/documents/{id}`; throws on failure. */
  async function refreshDocument(documentId: number): Promise<void> {
    replaceRow(toListItem(await getDocument(documentId)))
  }

  function remember(result: DocumentUploadResult): void {
    parseJobIds.value[result.document.id] = result.job_id
    replaceRow(result.document)
  }

  async function upload(file: File): Promise<DocumentUploadResult> {
    const result = await uploadDocument(file)
    remember(result)
    return result
  }

  async function importUrl(url: string): Promise<DocumentUploadResult> {
    const result = await importDocumentFromUrl(url)
    remember(result)
    return result
  }

  /**
   * Rename one document (`PATCH` with `title` only). The server's own row is
   * written back rather than the requested text, so a title it trimmed is what
   * the list then shows; a blank or over-long title comes back as 422 and is
   * thrown to the caller. The full detail is returned so a detail page can
   * update its header without a second request.
   */
  async function rename(documentId: number, title: string): Promise<DocumentDetail> {
    const updated = await patchDocument(documentId, { title })
    replaceRow(toListItem(updated))
    return updated
  }

  /**
   * Move one document into a folder, or out of every folder with `null`
   * (`PATCH` with `folder_id` only). A folder that no longer exists is a 404
   * and is thrown, so a stale sidebar cannot silently drop the document.
   */
  async function move(documentId: number, folderId: number | null): Promise<DocumentDetail> {
    const updated = await patchDocument(documentId, { folder_id: folderId })
    replaceRow(toListItem(updated))
    return updated
  }

  async function remove(documentId: number): Promise<void> {
    await deleteDocument(documentId)
    documents.value = documents.value.filter((item) => item.id !== documentId)
    delete parseJobIds.value[documentId]
  }

  function parseJobIdOf(documentId: number): number | null {
    return parseJobIds.value[documentId] ?? null
  }

  return {
    documents,
    loading,
    loadError,
    loaded,
    parseJobIds,
    hasUntrackedActiveDocument,
    load,
    ensureLoaded,
    refreshDocument,
    upload,
    importUrl,
    rename,
    move,
    remove,
    parseJobIdOf,
  }
})
