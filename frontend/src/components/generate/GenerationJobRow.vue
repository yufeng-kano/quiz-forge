<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
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

    <!-- Difficulty is a per-item fact (D31), so it rides on the item line -->
    <ul class="job-row__items">
      <li v-for="item in entry.items" :key="item.question_type" class="job-row__item">
        {{
          item.difficulty === undefined
            ? t('generate.jobs.item', {
                type: t(QUESTION_TYPE_LABEL_KEYS[item.question_type]),
                count: item.count,
              })
            : t('generate.jobs.itemWithDifficulty', {
                type: t(QUESTION_TYPE_LABEL_KEYS[item.question_type]),
                count: item.count,
                difficulty: item.difficulty,
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
        })
      }}
    </p>

    <p v-if="requestError !== null" class="form-error">{{ requestError }}</p>

    <div v-if="status === 'failed'" class="job-row__failure">
      <p class="form-error">{{ error ?? t('generate.jobs.failedNoDetail') }}</p>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :aria-label="t('generate.jobs.retry')"
        :title="t('generate.jobs.retry')"
        @click="retry"
      >
        <AppIcon name="refresh" :size="16" />
      </AppButton>
    </div>

    <template v-else-if="status === 'done'">
      <p v-if="error !== null" class="form-error">
        {{ t('generate.jobs.partialError', { error }) }}
      </p>
      <p>
        <RouterLink :to="{ name: 'review' }">{{ t('generate.jobs.goReview') }}</RouterLink>
      </p>
    </template>

    <p v-else-if="job === null" class="muted-text">{{ t('job.progress.notStarted') }}</p>
  </article>
</template>

<style scoped>
/* One entry of the history column: the list divides its rows with a hairline,
   so the row itself carries no border, radius or surface of its own
   (docs/frontend.md 設計節制原則: 卡片不是骨架) */
.job-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
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
  gap: var(--space-1) var(--space-4);
  padding: 0;
  list-style: none;
}

.job-row__item {
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

/* Secondary line of the row (id, time, scope, difficulty): the app's muted
   tone at its readable size, never a shrunken grey line */
.job-row__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.job-row__failure {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.job-row__failure .form-error {
  flex: 1;
  min-width: 0;
}
</style>
