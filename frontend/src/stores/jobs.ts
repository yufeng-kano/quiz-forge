/**
 * Shared source of truth for background-task state.
 *
 * It lives in Pinia rather than a `setInterval` inside each component
 * (docs/frontend.md: cross-page state belongs in a store) because:
 * - the same job shown by several components only costs one request, tracked
 *   by a subscriber count;
 * - navigating back to a page shows the last known state immediately instead
 *   of blanking out and refetching;
 * - polling stops when the job reaches `done` / `failed` or when the last
 *   subscriber leaves, so no orphan timers are left behind.
 *
 * Components do not use this store directly — they go through `useJobPolling()`.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { JOB_POLL_INTERVAL_MS, getJob, isTerminalJobStatus, retryJob, type Job } from '@/api'
import { translateApiError } from '@/i18n/errors'

interface PollEntry {
  /** How many components are currently watching this job. */
  subscribers: number
  timer: ReturnType<typeof setTimeout> | null
  /** Guards against firing the next request before the previous one returns. */
  inFlight: boolean
}

export const useJobsStore = defineStore('jobs', () => {
  /** Last successfully fetched job payload, keyed by job id. */
  const jobs = ref<Record<number, Job>>({})
  /**
   * Localised message for a failed poll *request* (backend unreachable, 500, …).
   * This is not `job.error`, which is the failure reason of the task itself.
   */
  const requestErrors = ref<Record<number, string | null>>({})

  // Pure timer bookkeeping; deliberately kept out of the reactive state.
  const entries = new Map<number, PollEntry>()

  function entryOf(jobId: number): PollEntry {
    let entry = entries.get(jobId)
    if (entry === undefined) {
      entry = { subscribers: 0, timer: null, inFlight: false }
      entries.set(jobId, entry)
    }
    return entry
  }

  function clearTimer(entry: PollEntry): void {
    if (entry.timer !== null) {
      clearTimeout(entry.timer)
      entry.timer = null
    }
  }

  function isFinished(jobId: number): boolean {
    const job = jobs.value[jobId]
    return job !== undefined && isTerminalJobStatus(job.status)
  }

  /**
   * Fetch the current state once. A failure is recorded in `requestErrors`
   * instead of being rethrown, so a transient error does not kill the polling
   * loop; the message stays visible until the next successful poll clears it.
   */
  async function refresh(jobId: number): Promise<void> {
    try {
      jobs.value[jobId] = await getJob(jobId)
      requestErrors.value[jobId] = null
    } catch (error) {
      requestErrors.value[jobId] = translateApiError(error)
    }
  }

  function schedule(jobId: number): void {
    const entry = entryOf(jobId)
    if (entry.timer !== null) {
      return
    }
    entry.timer = setTimeout(() => {
      entry.timer = null
      void poll(jobId)
    }, JOB_POLL_INTERVAL_MS)
  }

  async function poll(jobId: number): Promise<void> {
    const entry = entryOf(jobId)
    if (entry.subscribers === 0 || entry.inFlight) {
      return
    }
    entry.inFlight = true
    try {
      await refresh(jobId)
    } finally {
      entry.inFlight = false
    }
    if (entry.subscribers > 0 && !isFinished(jobId)) {
      schedule(jobId)
    }
  }

  /** Add a subscriber; the first one fetches immediately and starts the loop. */
  function track(jobId: number): void {
    const entry = entryOf(jobId)
    entry.subscribers += 1
    if (entry.subscribers > 1) {
      return
    }
    if (isFinished(jobId)) {
      return
    }
    void poll(jobId)
  }

  /**
   * Remove a subscriber. With none left the loop stops, but the last known
   * state is kept as a cache for the next page that asks for this job.
   */
  function release(jobId: number): void {
    const entry = entries.get(jobId)
    if (entry === undefined) {
      return
    }
    entry.subscribers = Math.max(0, entry.subscribers - 1)
    if (entry.subscribers === 0) {
      clearTimer(entry)
    }
  }

  /** Retry a failed job and resume polling once it is queued again. */
  async function retry(jobId: number): Promise<void> {
    try {
      jobs.value[jobId] = await retryJob(jobId)
      requestErrors.value[jobId] = null
    } catch (error) {
      requestErrors.value[jobId] = translateApiError(error)
      return
    }
    if (entryOf(jobId).subscribers > 0 && !isFinished(jobId)) {
      schedule(jobId)
    }
  }

  return { jobs, requestErrors, track, release, refresh, retry }
})
