/**
 * The 任務中心 list: every job the backend knows about, newest first.
 *
 * It is separate from `stores/jobs.ts`, which tracks *one* job at a time for
 * the components that watch a task they started. This store owns the opposite
 * view — a filtered page of many jobs — and keeps the filters in Pinia so
 * leaving 任務中心 and coming back does not reset them (docs/frontend.md:
 * cross-page state belongs in a store).
 *
 * Read failures are stored (the list renders around them); `retry` throws, so
 * the view can report the outcome of the user's own click as a toast.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  JOB_LIST_LIMIT,
  isTerminalJobStatus,
  listJobs,
  retryJob,
  type Job,
  type JobListQuery,
  type JobStatus,
} from '@/api'
import { translateApiError } from '@/i18n/errors'

export const useJobListStore = defineStore('jobList', () => {
  const jobs = ref<Job[]>([])
  /** True only while a load the user is waiting on runs; polls are silent. */
  const loading = ref(false)
  const loaded = ref(false)
  const loadError = ref<string | null>(null)

  const statusFilter = ref<JobStatus | null>(null)
  const kindFilter = ref<string | null>(null)

  const hasActiveJob = computed(() => jobs.value.some((job) => !isTerminalJobStatus(job.status)))

  function query(): JobListQuery {
    const params: JobListQuery = { limit: JOB_LIST_LIMIT }
    if (statusFilter.value !== null) {
      params.status = statusFilter.value
    }
    if (kindFilter.value !== null) {
      params.kind = kindFilter.value
    }
    return params
  }

  async function load(options: { silent?: boolean } = {}): Promise<void> {
    if (!(options.silent ?? false)) {
      loading.value = true
    }
    try {
      jobs.value = await listJobs(query())
      loaded.value = true
      loadError.value = null
    } catch (error) {
      loadError.value = translateApiError(error)
    } finally {
      loading.value = false
    }
  }

  function setStatusFilter(status: JobStatus | null): void {
    statusFilter.value = status
  }

  function setKindFilter(kind: string | null): void {
    kindFilter.value = kind
  }

  /**
   * Put a failed job back in the queue and replace the row with the server's
   * answer. Throws on failure so the caller can show it next to the button.
   */
  async function retry(jobId: number): Promise<Job> {
    const job = await retryJob(jobId)
    const index = jobs.value.findIndex((existing) => existing.id === job.id)
    if (index !== -1) {
      jobs.value.splice(index, 1, job)
    }
    return job
  }

  return {
    jobs,
    loading,
    loaded,
    loadError,
    statusFilter,
    kindFilter,
    hasActiveJob,
    load,
    setStatusFilter,
    setKindFilter,
    retry,
  }
})
