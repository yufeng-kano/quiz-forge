<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  DASHBOARD_RECENT_JOB_LIMIT,
  JOB_LIST_POLL_INTERVAL_MS,
  getStats,
  isTerminalJobStatus,
  listJobs,
  type Job,
  type Stats,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import StatCard from '@/components/ui/StatCard.vue'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { jobKindLabel } from '@/jobs/labels'

/**
 * 總覽 — where a session starts: what is in the system, what is waiting for the
 * user, and what the background is doing right now
 * (docs/decisions/2026-08-15-ux-overhaul-feature-expansion.md F5).
 *
 * Both requests are aggregates, so the page reloads them wholesale instead of
 * patching pieces. It refreshes itself only while a listed job is still
 * pending or running — an idle system produces no traffic.
 */
const { t } = useAppI18n()

const stats = ref<Stats | null>(null)
const recentJobs = ref<Job[]>([])
const loading = ref(false)
const loaded = ref(false)
const loadError = ref<string | null>(null)

/** Placeholder rows shown while the recent-activity block loads. */
const RECENT_SKELETON_ROWS = 4

/** Status order used for the breakdown chips, so the cards read the same way every time. */
const STATUS_ORDER = [
  'pending',
  'processing',
  'running',
  'ready',
  'done',
  'draft',
  'approved',
  'rejected',
  'failed',
]

interface StatusCount {
  status: string
  count: number
}

/** Known statuses first in pipeline order, then anything the backend added since. */
function statusCounts(byStatus: Record<string, number> | undefined): StatusCount[] {
  if (byStatus === undefined) {
    return []
  }
  return Object.entries(byStatus)
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => {
      const indexA = STATUS_ORDER.indexOf(a.status)
      const indexB = STATUS_ORDER.indexOf(b.status)
      if (indexA === indexB) {
        return a.status.localeCompare(b.status)
      }
      return (
        (indexA === -1 ? STATUS_ORDER.length : indexA) -
        (indexB === -1 ? STATUS_ORDER.length : indexB)
      )
    })
}

function sumOf(byStatus: Record<string, number> | undefined): number {
  return byStatus === undefined
    ? 0
    : Object.values(byStatus).reduce((total, count) => total + count, 0)
}

const documentCounts = computed(() => statusCounts(stats.value?.documents_by_status))
const questionCounts = computed(() => statusCounts(stats.value?.questions_by_status))

const documentTotal = computed(() => sumOf(stats.value?.documents_by_status))
const questionTotal = computed(() => sumOf(stats.value?.questions_by_status))
const draftCount = computed(() => stats.value?.questions_by_status['draft'] ?? 0)
const approvedCount = computed(() => stats.value?.questions_by_status['approved'] ?? 0)
const failedJobCount = computed(() => stats.value?.failed_job_count ?? 0)
const totalTokens = computed(() =>
  stats.value === null ? 0 : stats.value.llm_prompt_tokens + stats.value.llm_completion_tokens,
)

const hasActiveJob = computed(() =>
  recentJobs.value.some((job) => !isTerminalJobStatus(job.status)),
)

let timer: ReturnType<typeof setTimeout> | null = null

function clearTimer(): void {
  if (timer !== null) {
    clearTimeout(timer)
    timer = null
  }
}

function schedule(): void {
  if (timer !== null || !hasActiveJob.value) {
    return
  }
  timer = setTimeout(() => {
    timer = null
    void load({ silent: true })
  }, JOB_LIST_POLL_INTERVAL_MS)
}

async function load(options: { silent?: boolean } = {}): Promise<void> {
  if (!(options.silent ?? false)) {
    loading.value = true
  }
  try {
    const [statsResult, jobsResult] = await Promise.all([
      getStats(),
      listJobs({ limit: DASHBOARD_RECENT_JOB_LIMIT }),
    ])
    stats.value = statsResult
    recentJobs.value = jobsResult
    loaded.value = true
    loadError.value = null
  } catch (error) {
    loadError.value = translateApiError(error)
  } finally {
    loading.value = false
    schedule()
  }
}

onMounted(() => {
  void load()
})

onUnmounted(clearTimer)
</script>

<template>
  <div class="page">
    <PageHeader :title="t('pages.dashboard.title')" :subtitle="t('pages.dashboard.description')">
      <template #actions>
        <AppButton variant="secondary" :disabled="loading" @click="load()">
          {{ t('dashboard.refresh') }}
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="loadError !== null" class="error-banner">
      {{ loadError }}
      <AppButton variant="secondary" @click="load()">{{ t('dashboard.refresh') }}</AppButton>
    </p>

    <section class="dashboard__cards">
      <StatCard
        :label="t('dashboard.cards.documents')"
        :value="formatCount(documentTotal)"
        :to="{ name: 'documents' }"
        :loading="loading"
      >
        <span v-for="entry in documentCounts" :key="entry.status" class="dashboard__chip">
          <StatusBadge :status="entry.status" />
          {{ formatCount(entry.count) }}
        </span>
      </StatCard>

      <StatCard
        :label="t('dashboard.cards.drafts')"
        :value="formatCount(draftCount)"
        :hint="draftCount > 0 ? t('dashboard.cards.draftsCta') : t('dashboard.cards.draftsIdle')"
        :tone="draftCount > 0 ? 'attention' : 'default'"
        :to="{ name: 'review' }"
        :loading="loading"
      />

      <StatCard
        :label="t('dashboard.cards.questions')"
        :value="formatCount(questionTotal)"
        :hint="t('dashboard.cards.questionsHint', { count: approvedCount })"
        :to="{ name: 'questions' }"
        :loading="loading"
      >
        <span v-for="entry in questionCounts" :key="entry.status" class="dashboard__chip">
          <StatusBadge :status="entry.status" />
          {{ formatCount(entry.count) }}
        </span>
      </StatCard>

      <StatCard
        :label="t('dashboard.cards.chunks')"
        :value="formatCount(stats?.chunk_count ?? 0)"
        :hint="t('dashboard.cards.chunksHint', { count: stats?.category_count ?? 0 })"
        :loading="loading"
      />

      <StatCard
        :label="t('dashboard.cards.failedJobs')"
        :value="formatCount(failedJobCount)"
        :hint="
          failedJobCount > 0
            ? t('dashboard.cards.failedJobsCta')
            : t('dashboard.cards.failedJobsIdle')
        "
        :tone="failedJobCount > 0 ? 'attention' : 'default'"
        :to="{ name: 'jobs' }"
        :loading="loading"
      />

      <StatCard
        :label="t('dashboard.cards.tokens')"
        :value="formatCount(totalTokens)"
        :hint="t('dashboard.cards.tokensHint', { count: stats?.llm_call_count ?? 0 })"
        :to="{ name: 'usage' }"
        :loading="loading"
      />
    </section>

    <section class="card dashboard__recent">
      <header class="dashboard__recent-head">
        <h2 class="card-title">{{ t('dashboard.recent.title') }}</h2>
        <RouterLink class="dashboard__all" :to="{ name: 'jobs' }">
          {{ t('dashboard.recent.viewAll') }}
        </RouterLink>
      </header>

      <ul v-if="loading" class="dashboard__recent-list">
        <li v-for="index in RECENT_SKELETON_ROWS" :key="`skeleton-${index}`" class="dashboard__job">
          <AppSkeleton width="60%" />
        </li>
      </ul>

      <ul v-else-if="recentJobs.length > 0" class="dashboard__recent-list">
        <li v-for="job in recentJobs" :key="job.id" class="dashboard__job">
          <span class="dashboard__job-kind">{{ jobKindLabel(job.kind) }}</span>
          <StatusBadge :status="job.status" />
          <ProgressText v-if="!isTerminalJobStatus(job.status)" :progress="job.progress" />
          <span class="dashboard__job-meta">
            {{
              t('dashboard.recent.meta', { id: job.id, datetime: formatDateTime(job.updated_at) })
            }}
          </span>
        </li>
      </ul>

      <p v-else-if="loaded" class="muted-text">{{ t('dashboard.recent.empty') }}</p>
    </section>
  </div>
</template>

<style scoped>
.dashboard__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: var(--space-3);
}

.dashboard__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-variant-numeric: tabular-nums;
}

.dashboard__recent {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.dashboard__recent-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.dashboard__all {
  font-size: var(--font-size-md);
}

.dashboard__recent-list {
  display: flex;
  flex-direction: column;
  list-style: none;
  padding: 0;
}

.dashboard__job {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--font-size-md);
}

.dashboard__job:last-child {
  border-bottom: none;
}

.dashboard__job-kind {
  color: var(--color-heading);
  font-weight: 600;
}

.dashboard__job-meta {
  margin-left: auto;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}
</style>
