/**
 * Load one document and keep it fresh while its pipeline is still running.
 *
 * Job polling (`useJobPolling`) reports how far a job got, but the per-page
 * statuses and the parsed Markdown only appear in the document itself, so this
 * composable refetches `GET /api/v1/documents/{id}` on its own interval.
 *
 * It polls while any of these hold, and stops as soon as none do:
 * - the document status is still `pending` / `processing`;
 * - any page is — which covers a single-page retry, whose job may still be
 *   queued when the document itself is already `ready`;
 * - `keepPolling` says a job the caller is watching is still active.
 *
 * Like `useJobPolling`, a failed refetch is recorded rather than thrown, so one
 * hiccup does not end the loop, and the effect scope's disposal stops the timer.
 */

import {
  computed,
  onScopeDispose,
  ref,
  toValue,
  watch,
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

import { DOCUMENT_POLL_INTERVAL_MS, getDocument, isActiveEntityStatus } from '@/api'
import type { DocumentDetail } from '@/api'
import { translateApiError } from '@/i18n/errors'

export interface UseDocumentDetailOptions {
  /** Keep polling even when the document itself looks settled. */
  keepPolling?: MaybeRefOrGetter<boolean>
}

export interface UseDocumentDetailResult {
  detail: Ref<DocumentDetail | null>
  /** True only for a load the user is waiting on, never for a background poll. */
  loading: Ref<boolean>
  error: Ref<string | null>
  /** The document or one of its pages is still being worked on. */
  isProcessing: ComputedRef<boolean>
  /** Refetch and show the loading state. */
  reload: () => Promise<void>
  /** Refetch in the background, leaving the current content on screen. */
  refresh: () => Promise<void>
}

export function useDocumentDetail(
  documentId: MaybeRefOrGetter<number | null>,
  options: UseDocumentDetailOptions = {},
): UseDocumentDetailResult {
  const detail = ref<DocumentDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let timer: ReturnType<typeof setTimeout> | null = null
  let inFlight = false
  let disposed = false

  const isProcessing = computed<boolean>(() => {
    const current = detail.value
    if (current === null) {
      return false
    }
    return (
      isActiveEntityStatus(current.status) ||
      current.pages.some((page) => isActiveEntityStatus(page.status))
    )
  })

  const shouldPoll = computed<boolean>(() => {
    if (disposed || toValue(documentId) === null) {
      return false
    }
    return isProcessing.value || toValue(options.keepPolling ?? false)
  })

  function clearTimer(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  async function fetchOnce(silent: boolean): Promise<void> {
    const requestedId = toValue(documentId)
    if (requestedId === null) {
      return
    }
    if (!silent) {
      loading.value = true
    }
    try {
      const response = await getDocument(requestedId)
      // The id can change mid-request when the user navigates between
      // documents; a late response must not overwrite the new one.
      if (toValue(documentId) === requestedId) {
        detail.value = response
        error.value = null
      }
    } catch (cause) {
      if (toValue(documentId) === requestedId) {
        error.value = translateApiError(cause)
      }
    } finally {
      if (!silent) {
        loading.value = false
      }
    }
  }

  function schedule(): void {
    // `disposed` is checked directly: it is not reactive, so a cached
    // `shouldPoll` could still read `true` for a request that was in flight
    // when the scope went away, which would restart the loop forever.
    if (disposed || timer !== null || !shouldPoll.value) {
      return
    }
    timer = setTimeout(() => {
      timer = null
      void tick()
    }, DOCUMENT_POLL_INTERVAL_MS)
  }

  async function tick(): Promise<void> {
    if (disposed || inFlight || !shouldPoll.value) {
      return
    }
    inFlight = true
    try {
      await fetchOnce(true)
    } finally {
      inFlight = false
    }
    schedule()
  }

  async function reload(): Promise<void> {
    await fetchOnce(false)
    schedule()
  }

  async function refresh(): Promise<void> {
    await fetchOnce(true)
    schedule()
  }

  watch(
    () => toValue(documentId),
    (id) => {
      clearTimer()
      detail.value = null
      error.value = null
      if (id !== null) {
        void reload()
      }
    },
    { immediate: true },
  )

  // Covers the transitions the fetch loop cannot see by itself: a retry that
  // just put a page back to work, or a job the caller started.
  watch(shouldPoll, (active) => {
    if (active) {
      schedule()
    } else {
      clearTimer()
    }
  })

  onScopeDispose(() => {
    disposed = true
    clearTimer()
  })

  return { detail, loading, error, isProcessing, reload, refresh }
}
