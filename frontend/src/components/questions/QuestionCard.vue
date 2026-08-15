<script setup lang="ts">
import { computed } from 'vue'

import type { QuestionListItem } from '@/api'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { questionDifficultyLabel, questionTypeLabel } from '@/questions/labels'

/**
 * The card frame shared by 審題 and 題庫: type label, difficulty, status badge
 * and the id/timestamp line, with the question itself and the page's own
 * controls supplied through slots.
 *
 * `select` renders in front of the header (the export checkbox on 題庫),
 * `actions` on the right of it, and `footer` under the body — the source-text
 * panel and error messages of the review page.
 */
const props = defineProps<{ question: QuestionListItem }>()

const { t } = useAppI18n()

const typeLabel = computed(() => questionTypeLabel(props.question.type))

const difficultyLabel = computed(() => questionDifficultyLabel(props.question.difficulty))
</script>

<template>
  <article class="question-card">
    <header class="question-card__header">
      <div v-if="$slots.select" class="question-card__select">
        <slot name="select" />
      </div>

      <div class="question-card__meta">
        <span class="question-card__type">{{ typeLabel }}</span>
        <span class="question-card__difficulty">{{ difficultyLabel }}</span>
        <StatusBadge :status="question.status" />
      </div>

      <div v-if="$slots.actions" class="question-card__actions">
        <slot name="actions" />
      </div>
    </header>

    <p class="question-card__identity">
      {{
        t('questions.card.identity', {
          id: question.id,
          datetime: formatDateTime(question.created_at),
        })
      }}
    </p>

    <div class="question-card__content">
      <slot />
    </div>

    <slot name="footer" />
  </article>
</template>

<style scoped>
.question-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

.question-card__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
}

.question-card__select {
  display: flex;
  align-items: center;
}

.question-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
}

.question-card__type {
  color: var(--color-heading);
  font-weight: 600;
}

.question-card__difficulty {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.question-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-left: auto;
}

.question-card__identity {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
}

.question-card__content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
