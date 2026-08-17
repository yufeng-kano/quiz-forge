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
import AppIcon from '@/components/ui/AppIcon.vue'
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
    width: '2.75rem',
  },
])

/** Tooltip and accessible name of the icon-only retry button. */
function retryLabel(job: Job): string {
  return retryingJobId.value === job.id ? t('jobs.retrying') : t('jobs.retry')
}

/** A finished job may still carry its final count (`40/40 pages`), worth showing. */
function hasProgress(job: Job): boolean {
  return (job.progress ?? '') !== ''
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
  <div class="page page--workspace">
    <PageHeader :page-name="t('nav.jobs')">
      <template #actions>
        <AppButton
          variant="secondary"
          icon
          :disabled="store.loading"
          :aria-label="t('jobs.refresh')"
          :title="t('jobs.refresh')"
          @click="store.load()"
        >
          <AppIcon name="refresh" />
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="store.loadError !== null" class="error-banner">{{ store.loadError }}</p>

    <div class="workspace">
      <div class="workspace__toolbar">
        <select
          v-model="selectedStatus"
          class="form-select workspace__filter"
          :aria-label="t('jobs.filters.status')"
        >
          <option value="">{{ t('jobs.filters.anyStatus') }}</option>
          <option v-for="status in statusOptions" :key="status" :value="status">
            {{ t(`status.${status}`) }}
          </option>
        </select>

        <select
          v-model="selectedKind"
          class="form-select workspace__filter"
          :aria-label="t('jobs.filters.kind')"
        >
          <option value="">{{ t('jobs.filters.anyKind') }}</option>
          <option v-for="kind in kindOptions" :key="kind" :value="kind">
            {{ jobKindLabel(kind) }}
          </option>
        </select>
      </div>

      <DataTable
        :columns="columns"
        :rows="store.jobs"
        :row-key="(job: Job) => job.id"
        :loading="store.loading"
        :empty-title="t('jobs.emptyTitle')"
        fill-height
      >
        <template #status="{ row }">
          <StatusBadge :status="row.status" />
        </template>

        <template #progress="{ row }">
          <ProgressText
            v-if="hasProgress(row) || !isTerminalJobStatus(row.status)"
            :progress="row.progress"
          />
        </template>

        <template #error="{ row }">
          <span
            v-if="row.error !== null && row.error !== ''"
            class="jobs__error text-ellipsis"
            :title="row.error"
          >
            {{ row.error }}
          </span>
        </template>

        <template #actions="{ row }">
          <AppButton
            v-if="row.status === 'failed'"
            variant="ghost"
            icon
            size="sm"
            :disabled="retryingJobId === row.id"
            :aria-label="retryLabel(row)"
            :title="retryLabel(row)"
            @click="onRetry(row)"
          >
            <AppIcon name="refresh" :size="16" />
          </AppButton>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<style scoped>
.page > .error-banner {
  margin: var(--space-3) 0 0;
}

.workspace {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.workspace__toolbar {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-3) 0;
}

.workspace__filter {
  width: 11rem;
}

.jobs__error {
  min-width: 0;
  width: 100%;
  color: var(--color-status-failed-text);
}
</style>
