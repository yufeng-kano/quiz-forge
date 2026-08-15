<script setup lang="ts">
import type { ComparisonPayload } from '@/api'
import QuestionAnswerBlock from '@/components/questions/QuestionAnswerBlock.vue'
import { useAppI18n } from '@/i18n'

/**
 * `comparison` — docs/question-bank.md 比較題.
 *
 * The model answer is structured, not free text, so the differences are shown
 * as the 面向 × A × B table the answer sheet renders (docs/question-bank.md:
 * 答案結構化成異同表). The table scrolls inside its own container rather than
 * widening the card.
 */
defineProps<{ payload: ComparisonPayload }>()

const { t } = useAppI18n()
</script>

<template>
  <div class="question-body">
    <p class="question-stem">{{ payload.stem }}</p>

    <p class="comparison__subjects">
      <span class="comparison__subject">{{ payload.subject_a }}</span>
      <span class="comparison__vs">/</span>
      <span class="comparison__subject">{{ payload.subject_b }}</span>
    </p>

    <div class="comparison__aspects">
      <span class="comparison__aspects-label">{{ t('questions.labels.aspects') }}</span>
      <span v-for="(aspect, index) in payload.aspects" :key="index" class="comparison__aspect">
        {{ aspect }}
      </span>
    </div>

    <QuestionAnswerBlock :label="t('questions.labels.similarities')">
      <ul v-if="payload.model_answer.similarities.length > 0" class="question-bullets">
        <li v-for="(item, index) in payload.model_answer.similarities" :key="index">{{ item }}</li>
      </ul>
      <p v-else class="form-hint">{{ t('questions.labels.noSimilarities') }}</p>
    </QuestionAnswerBlock>

    <QuestionAnswerBlock :label="t('questions.labels.differences')">
      <div class="comparison__table-scroll">
        <table class="comparison__table">
          <thead>
            <tr>
              <th scope="col">{{ t('questions.labels.aspect') }}</th>
              <th scope="col">{{ payload.subject_a }}</th>
              <th scope="col">{{ payload.subject_b }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in payload.model_answer.differences" :key="index">
              <th scope="row">{{ row.aspect }}</th>
              <td>{{ row.a }}</td>
              <td>{{ row.b }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </QuestionAnswerBlock>
  </div>
</template>

<style scoped>
.comparison__subjects {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.4rem;
}

.comparison__subject {
  color: var(--color-heading);
  font-weight: 600;
}

.comparison__vs {
  color: var(--color-text-muted);
}

.comparison__aspects {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.comparison__aspects-label {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

.comparison__aspect {
  padding: 0.05rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-background-soft);
  font-size: 0.8125rem;
}

.comparison__table-scroll {
  overflow-x: auto;
}

.comparison__table {
  min-width: 100%;
  border-collapse: collapse;
  background: var(--color-background);
}

.comparison__table th,
.comparison__table td {
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--color-border);
  text-align: left;
  vertical-align: top;
}

.comparison__table thead th {
  background: var(--color-background-soft);
  color: var(--color-heading);
  font-weight: 600;
}

.comparison__table tbody th {
  color: var(--color-heading);
  font-weight: 600;
  white-space: nowrap;
}
</style>
