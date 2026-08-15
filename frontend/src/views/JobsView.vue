<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  JOB_KINDS,
  JOB_LIST_POLL_INTERVAL_MS,
  JOB_STATUSES,
  isTerminalJobStatus,
  type Job,
  type JobStatus,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import DataTable from '@/components/ui/DataTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DataTableColumn } from '@/components/ui/dataTable'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { jobKindLabel } from '@/jobs/labels'
import { useJobListStore } from '@/stores/jobList'
import { useToastsStore } from '@/stores/toasts'

/**
 * 任務中心 — every background job in one place, with the minimal-unit retry the
 * .rule UX rules require (a failed job goes back to `pending`; nothing else is
 * re-run).
 *
 * The list polls itself only while at least one listed job is still pending or
 * running, so an idle system is quiet.
 */
const { t } = useAppI18n()
const store = useJobListStore()
const toasts = useToastsStore()

/** Characters of `jobs.error` shown before the row offers to expand it. */
const ERROR_PREVIEW_LENGTH = 90

const expandedErrorIds = ref<number[]>([])
const retryingJobId = ref<number | null>(null)

const statusOptions = JOB_STATUSES
const kindOptions = JOB_KINDS

const selectedStatus = computed<JobStatus | ''>({
  get: () => store.statusFilter ?? '',
  set: (value) => store.setStatusFilter(value === '' ? null : value),
})

const selectedKind = computed<string>({
  get: () => store.kindFilter ?? '',
  set: (value) => store.setKindFilter(value === '' ? null : value),
})

const columns = computed<DataTableColumn<Job>[]>(() => [
  {
    key: 'id',
    label: t('jobs.columns.id'),
    value: (job) => `#${job.id}`,
    sortValue: (job) => job.id,
    width: '5.5rem',
    nowrap: true,
  },
  {
    key: 'kind',
    label: t('jobs.columns.kind'),
    value: (job) => jobKindLabel(job.kind),
    sortValue: (job) => jobKindLabel(job.kind),
  },
  {
    key: 'status',
    label: t('jobs.columns.status'),
    sortValue: (job) => job.status,
    width: '7rem',
    nowrap: true,
  },
  { key: 'progress', label: t('jobs.columns.progress'), width: '10rem' },
  { key: 'error', label: t('jobs.columns.error') },
  {
    key: 'created_at',
    label: t('jobs.columns.createdAt'),
    value: (job) => formatDateTime(job.created_at),
    sortValue: (job) => job.created_at,
    width: '10rem',
    nowrap: true,
  },
  {
    key: 'updated_at',
    label: t('jobs.columns.updatedAt'),
    value: (job) => formatDateTime(job.updated_at),
    sortValue: (job) => job.updated_at,
    width: '10rem',
    nowrap: true,
  },
  {
    key: 'actions',
    label: t('jobs.columns.actions'),
    labelHidden: true,
    align: 'end',
    width: '7rem',
    nowrap: true,
  },
])

/** A finished job may still carry its final count (`40/40 pages`), worth showing. */
function hasProgress(job: Job): boolean {
  return (job.progress ?? '') !== ''
}

function errorPreview(job: Job): string {
  const error = job.error ?? ''
  return error.length > ERROR_PREVIEW_LENGTH ? `${error.slice(0, ERROR_PREVIEW_LENGTH)}…` : error
}

function isTruncated(job: Job): boolean {
  return (job.error ?? '').length > ERROR_PREVIEW_LENGTH
}

function isExpanded(job: Job): boolean {
  return expandedErrorIds.value.includes(job.id)
}

function toggleError(job: Job): void {
  expandedErrorIds.value = isExpanded(job)
    ? expandedErrorIds.value.filter((id) => id !== job.id)
    : [...expandedErrorIds.value, job.id]
}

async function onRetry(job: Job): Promise<void> {
  retryingJobId.value = job.id
  try {
    await store.retry(job.id)
    toasts.success(t('jobs.retryQueued', { id: job.id }))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    retryingJobId.value = null
  }
}

let timer: ReturnType<typeof setTimeout> | null = null

function clearTimer(): void {
  if (timer !== null) {
    clearTimeout(timer)
    timer = null
  }
}

function schedule(): void {
  if (timer !== null || !store.hasActiveJob) {
    return
  }
  timer = setTimeout(() => {
    timer = null
    void tick()
  }, JOB_LIST_POLL_INTERVAL_MS)
}

async function tick(): Promise<void> {
  if (!store.hasActiveJob) {
    return
  }
  await store.load({ silent: true })
  schedule()
}

watch(
  () => store.hasActiveJob,
  (active) => {
    if (active) {
      schedule()
    } else {
      clearTimer()
    }
  },
)

// A filter change is a new query, so it always goes back to the server.
watch([() => store.statusFilter, () => store.kindFilter], () => {
  void store.load({ silent: store.loaded })
})

onMounted(async () => {
  await store.load({ silent: store.loaded })
  schedule()
})

onUnmounted(clearTimer)
</script>

<template>
  <div class="page">
    <PageHeader :title="t('pages.jobs.title')" :subtitle="t('pages.jobs.description')">
      <template #actions>
        <AppButton variant="secondary" :disabled="store.loading" @click="store.load()">
          {{ t('jobs.refresh') }}
        </AppButton>
      </template>
    </PageHeader>

    <section class="card jobs__filters">
      <div class="form-field">
        <label class="form-label" for="jobs-status-filter">{{ t('jobs.filters.status') }}</label>
        <select id="jobs-status-filter" v-model="selectedStatus" class="form-select">
          <option value="">{{ t('jobs.filters.anyStatus') }}</option>
          <option v-for="status in statusOptions" :key="status" :value="status">
            {{ t(`status.${status}`) }}
          </option>
        </select>
      </div>

      <div class="form-field">
        <label class="form-label" for="jobs-kind-filter">{{ t('jobs.filters.kind') }}</label>
        <select id="jobs-kind-filter" v-model="selectedKind" class="form-select">
          <option value="">{{ t('jobs.filters.anyKind') }}</option>
          <option v-for="kind in kindOptions" :key="kind" :value="kind">
            {{ jobKindLabel(kind) }}
          </option>
        </select>
      </div>
    </section>

    <p v-if="store.loadError !== null" class="error-banner">
      {{ store.loadError }}
      <AppButton variant="secondary" @click="store.load()">{{ t('jobs.refresh') }}</AppButton>
    </p>

    <DataTable
      :columns="columns"
      :rows="store.jobs"
      :row-key="(job: Job) => job.id"
      :loading="store.loading"
      :empty-title="t('jobs.emptyTitle')"
      :empty-description="t('jobs.emptyDescription')"
    >
      <template #status="{ row }">
        <StatusBadge :status="row.status" />
      </template>

      <template #progress="{ row }">
        <ProgressText
          v-if="hasProgress(row) || !isTerminalJobStatus(row.status)"
          :progress="row.progress"
        />
        <span v-else class="jobs__muted">{{ t('jobs.none') }}</span>
      </template>

      <template #error="{ row }">
        <div v-if="row.error !== null && row.error !== ''" class="jobs__error">
          <p class="jobs__error-text">{{ isExpanded(row) ? row.error : errorPreview(row) }}</p>
          <AppButton v-if="isTruncated(row)" variant="ghost" size="sm" @click="toggleError(row)">
            {{ isExpanded(row) ? t('jobs.collapseError') : t('jobs.expandError') }}
          </AppButton>
        </div>
        <span v-else class="jobs__muted">{{ t('jobs.none') }}</span>
      </template>

      <template #actions="{ row }">
        <AppButton
          v-if="row.status === 'failed'"
          variant="secondary"
          size="sm"
          :disabled="retryingJobId === row.id"
          @click="onRetry(row)"
        >
          {{ retryingJobId === row.id ? t('jobs.retrying') : t('jobs.retry') }}
        </AppButton>
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.jobs__filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.jobs__filters .form-field {
  min-width: 12rem;
}

.jobs__muted {
  color: var(--color-text-faint);
}

.jobs__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  min-width: 12rem;
}

.jobs__error-text {
  color: var(--color-status-failed-text);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
