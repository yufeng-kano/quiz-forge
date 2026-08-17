<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { QUESTION_TYPE_LABEL_KEYS } from '@/questions/labels'
import type { GenerationJobEntry } from '@/stores/generation'

/**
 * One generation job launched in this session, with its live progress and the
 * 題型 × 數量 combos it was asked for.
 *
 * `jobs.error` is shown even on a `done` job: a generation job that finished
 * with some questions failing records the summary there and still counts as
 * done (docs/question-bank.md — 單題生成失敗不會使整個出題 job 失敗), so hiding it
 * would hide the fact that fewer questions arrived than were asked for.
 */
const props = defineProps<{ entry: GenerationJobEntry }>()

const { t } = useAppI18n()

const { job, status, progress, error, requestError, isActive, retry } = useJobPolling(
  () => props.entry.jobId,
)

const difficultyLabel = computed(() =>
  props.entry.difficulty === null
    ? t('questions.difficulty.unspecified')
    : t('questions.difficulty.prefix', { difficulty: props.entry.difficulty }),
)
</script>

<template>
  <article class="job-row">
    <div class="job-row__head">
      <span class="job-row__summary">
        {{ t('generate.jobs.total', { count: entry.totalCount }) }}
      </span>
      <StatusBadge v-if="status !== null" :status="status" />
      <ProgressText v-if="isActive" :progress="progress" />
    </div>

    <ul class="job-row__items">
      <li v-for="item in entry.items" :key="item.question_type" class="job-row__item">
        {{
          t('generate.jobs.item', {
            type: t(QUESTION_TYPE_LABEL_KEYS[item.question_type]),
            count: item.count,
          })
        }}
      </li>
    </ul>

    <p class="job-row__meta">
      {{
        t('generate.jobs.meta', {
          id: entry.jobId,
          datetime: formatDateTime(entry.submittedAt),
          documents: entry.documentCount,
          categories: entry.categoryCount,
          difficulty: difficultyLabel,
        })
      }}
    </p>

    <p v-if="requestError !== null" class="form-error">{{ requestError }}</p>

    <template v-if="status === 'failed'">
      <p class="form-error">
        {{
          error === null ? t('generate.jobs.failedNoDetail') : t('generate.jobs.failed', { error })
        }}
      </p>
      <div>
        <AppButton variant="secondary" @click="retry">{{ t('generate.jobs.retry') }}</AppButton>
      </div>
    </template>

    <template v-else-if="status === 'done'">
      <p v-if="error !== null" class="form-error">
        {{ t('generate.jobs.partialError', { error }) }}
      </p>
      <p class="job-row__done">
        {{ t('generate.jobs.done') }}
        <RouterLink class="job-row__link" :to="{ name: 'review' }">
          {{ t('generate.jobs.goReview') }}
        </RouterLink>
      </p>
    </template>

    <p v-else-if="job === null" class="form-hint">{{ t('job.progress.notStarted') }}</p>
  </article>
</template>

<style scoped>
/* The row sits inside the 生成紀錄 card, so it reads as a nested entry — a
   hairline border on the soft surface — rather than a second card on top of one */
.job-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-background-soft);
}

.job-row__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.job-row__summary {
  color: var(--color-heading);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.job-row__items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-2);
  padding: 0;
  list-style: none;
}

.job-row__item {
  color: var(--color-text);
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

.job-row__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.job-row__done {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  color: var(--color-status-done-text);
}

.job-row__link {
  color: var(--color-accent);
}
</style>
