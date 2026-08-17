<script setup lang="ts">
import { computed } from 'vue'

import type { QuestionListItem } from '@/api'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppI18n } from '@/i18n'
import { questionDifficultyLabel, questionTypeLabel } from '@/questions/labels'

/**
 * The question row shared by 審題 and 題庫: type label, id and difficulty on one
 * header line, with the question itself and the page's own controls supplied
 * through slots.
 *
 * `select` renders in front of the header (the export checkbox on 題庫),
 * `actions` on the right of it, and `footer` under the body — the source-text
 * panel and error messages of the review page.
 *
 * Both queues are lists of questions divided by a hairline, not stacks of
 * framed cards (docs/decisions/2026-08-17-bank-on-questions-page.md D12,
 * docs/frontend.md 設計節制原則 — 卡片不是骨架).
 *
 * `expectedStatus` is the status the list consists of by definition — `draft`
 * in 審題, `approved` in 題庫. The status is only rendered for a row that
 * deviates from it: repeating what the list already says is not information
 * (D19).
 *
 * The id stays because export failures name questions by it; the creation time
 * does not, because nothing on either page is ordered or filtered by it.
 */
const props = defineProps<{ question: QuestionListItem; expectedStatus: string }>()

const { t } = useAppI18n()

const typeLabel = computed(() => questionTypeLabel(props.question.type))

const difficultyLabel = computed(() => questionDifficultyLabel(props.question.difficulty))

const showStatus = computed(() => props.question.status !== props.expectedStatus)
</script>

<template>
  <article class="question-card">
    <header class="question-card__header">
      <div v-if="$slots.select" class="question-card__select">
        <slot name="select" />
      </div>

      <div class="question-card__meta">
        <span class="question-card__type">{{ typeLabel }}</span>
        <span class="question-card__id">{{ t('questions.card.id', { id: question.id }) }}</span>
        <span class="question-card__difficulty">{{ difficultyLabel }}</span>
        <StatusBadge v-if="showStatus" :status="question.status" />
      </div>

      <div v-if="$slots.actions" class="question-card__actions">
        <slot name="actions" />
      </div>
    </header>

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
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--color-hairline);
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

.question-card__id {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

.question-card__difficulty {
  color: var(--color-text-muted);
}

.question-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-left: auto;
}

.question-card__content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
