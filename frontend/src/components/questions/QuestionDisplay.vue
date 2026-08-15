<script setup lang="ts">
import { computed } from 'vue'

import type { QuestionListItem } from '@/api'
import AnalogyQuestion from '@/components/questions/AnalogyQuestion.vue'
import ComparisonQuestion from '@/components/questions/ComparisonQuestion.vue'
import FillBlankQuestion from '@/components/questions/FillBlankQuestion.vue'
import ShortAnswerQuestion from '@/components/questions/ShortAnswerQuestion.vue'
import SingleChoiceQuestion from '@/components/questions/SingleChoiceQuestion.vue'
import TrueFalseQuestion from '@/components/questions/TrueFalseQuestion.vue'
import { useAppI18n } from '@/i18n'
import { toTypedPayload } from '@/questions/payload'

/**
 * Picks the renderer for a question's type (docs/frontend.md: 題目渲染元件依題型
 * 分開實作). Both 審題 and 題庫 render through this component, so a question
 * looks the same wherever it is shown.
 *
 * A payload that does not match its type shows a notice instead: the row exists
 * in the database and hiding it would leave the reviewer unable to discard it.
 */
const props = defineProps<{ question: QuestionListItem }>()

const { t } = useAppI18n()

const typed = computed(() => toTypedPayload(props.question))

/**
 * One narrowing accessor per type. Comparing the discriminant inside each
 * computed is what lets the template pass a concretely typed payload down
 * without a cast.
 */
const comparison = computed(() => (typed.value?.type === 'comparison' ? typed.value.payload : null))
const analogy = computed(() => (typed.value?.type === 'analogy' ? typed.value.payload : null))
const singleChoice = computed(() =>
  typed.value?.type === 'single_choice' ? typed.value.payload : null,
)
const trueFalse = computed(() => (typed.value?.type === 'true_false' ? typed.value.payload : null))
const fillBlank = computed(() => (typed.value?.type === 'fill_blank' ? typed.value.payload : null))
const shortAnswer = computed(() =>
  typed.value?.type === 'short_answer' ? typed.value.payload : null,
)
</script>

<template>
  <ComparisonQuestion v-if="comparison !== null" :payload="comparison" />
  <AnalogyQuestion v-else-if="analogy !== null" :payload="analogy" />
  <SingleChoiceQuestion v-else-if="singleChoice !== null" :payload="singleChoice" />
  <TrueFalseQuestion v-else-if="trueFalse !== null" :payload="trueFalse" />
  <FillBlankQuestion v-else-if="fillBlank !== null" :payload="fillBlank" />
  <ShortAnswerQuestion v-else-if="shortAnswer !== null" :payload="shortAnswer" />
  <div v-else class="question-display__unreadable">
    <p class="question-display__unreadable-title">{{ t('questions.card.unreadableTitle') }}</p>
    <p class="form-hint">{{ t('questions.card.unreadableDescription') }}</p>
  </div>
</template>

<style scoped>
.question-display__unreadable {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-status-failed-border);
  border-radius: 6px;
  background: var(--color-status-failed-bg);
}

.question-display__unreadable-title {
  color: var(--color-status-failed-text);
  font-weight: 600;
}
</style>
