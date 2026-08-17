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
 *
 * `flush` is the bank-list variant (docs/decisions/2026-08-17-bank-on-questions-
 * page.md D12): no outer border or radius, just padding and a bottom hairline.
 * Review keeps the bordered card.
 */
const props = withDefaults(defineProps<{ question: QuestionListItem; flush?: boolean }>(), {
  flush: false,
})

const { t } = useAppI18n()

const typeLabel = computed(() => questionTypeLabel(props.question.type))

const difficultyLabel = computed(() => questionDifficultyLabel(props.question.difficulty))
</script>

<template>
  <article class="question-card" :class="{ 'question-card--flush': flush }">
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
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
}

.question-card--flush {
  padding: var(--space-4) 0;
  border: none;
  border-bottom: 1px solid var(--color-hairline);
  border-radius: 0;
}

.question-card__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.question-card__select {
  display: flex;
  align-items: center;
}

.question-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.question-card__type {
  color: var(--color-heading);
  font-weight: 600;
}

.question-card__difficulty {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.question-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-left: auto;
}

.question-card__identity {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

.question-card__content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
