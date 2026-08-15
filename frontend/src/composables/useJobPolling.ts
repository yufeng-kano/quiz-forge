/**
 * Subscribe to a single job's state.
 *
 * Usage: `const { status, progress, error } = useJobPolling(jobId)`.
 *
 * `jobId` may be a number, a ref or a getter. Changing the id (navigating
 * between `/documents/:id` pages, say) releases the old subscription and takes
 * out a new one; unmounting the component ends its effect scope and releases
 * too, at which point polling stops if nobody else is watching that job.
 */

import {
  computed,
  onScopeDispose,
  toValue,
  watch,
  type ComputedRef,
  type MaybeRefOrGetter,
} from 'vue'

import { isTerminalJobStatus, type Job, type JobStatus } from '@/api'
import { useJobsStore } from '@/stores/jobs'

export interface UseJobPollingResult {
  /** The last fetched job payload; null until the first response arrives. */
  job: ComputedRef<Job | null>
  status: ComputedRef<JobStatus | null>
  /** The job's textual progress, e.g. `12/40`. */
  progress: ComputedRef<string | null>
  /** Why the task itself failed (from `jobs.error`). */
  error: ComputedRef<string | null>
  /** Localised message for a failed poll request (backend unreachable, …). */
  requestError: ComputedRef<string | null>
  /** The job is still `pending` or `running`. */
  isActive: ComputedRef<boolean>
  refresh: () => Promise<void>
  retry: () => Promise<void>
}

export function useJobPolling(
  jobId: MaybeRefOrGetter<number | null | undefined>,
): UseJobPollingResult {
  const store = useJobsStore()

  const currentId = computed<number | null>(() => toValue(jobId) ?? null)

  const job = computed<Job | null>(() => {
    const id = currentId.value
    if (id === null) {
      return null
    }
    return store.jobs[id] ?? null
  })

  const status = computed<JobStatus | null>(() => job.value?.status ?? null)
  const progress = computed<string | null>(() => job.value?.progress ?? null)
  const error = computed<string | null>(() => job.value?.error ?? null)

  const requestError = computed<string | null>(() => {
    const id = currentId.value
    if (id === null) {
      return null
    }
    return store.requestErrors[id] ?? null
  })

  const isActive = computed<boolean>(() => {
    const current = status.value
    return current !== null && !isTerminalJobStatus(current)
  })

  watch(
    currentId,
    (id, previousId) => {
      if (previousId !== null && previousId !== undefined) {
        store.release(previousId)
      }
      if (id !== null) {
        store.track(id)
      }
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    if (currentId.value !== null) {
      store.release(currentId.value)
    }
  })

  async function refresh(): Promise<void> {
    const id = currentId.value
    if (id === null) {
      return
    }
    await store.refresh(id)
  }

  async function retry(): Promise<void> {
    const id = currentId.value
    if (id === null) {
      return
    }
    await store.retry(id)
  }

  return { job, status, progress, error, requestError, isActive, refresh, retry }
}
