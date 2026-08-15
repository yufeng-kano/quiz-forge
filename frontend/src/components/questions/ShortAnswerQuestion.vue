<script setup lang="ts">
import type { ShortAnswerPayload } from '@/api'
import QuestionAnswerBlock from '@/components/questions/QuestionAnswerBlock.vue'
import { useAppI18n } from '@/i18n'

/** `short_answer` — docs/question-bank.md 問答題. */
defineProps<{ payload: ShortAnswerPayload }>()

const { t } = useAppI18n()
</script>

<template>
  <div class="question-body">
    <p class="question-stem">{{ payload.stem }}</p>

    <QuestionAnswerBlock :label="t('questions.labels.modelAnswer')">
      <p class="short-answer__text">{{ payload.model_answer }}</p>
    </QuestionAnswerBlock>

    <QuestionAnswerBlock :label="t('questions.labels.keyPoints')" variant="explanation">
      <ul class="question-bullets">
        <li v-for="(point, index) in payload.key_points" :key="index">{{ point }}</li>
      </ul>
    </QuestionAnswerBlock>
  </div>
</template>

<style scoped>
.short-answer__text {
  white-space: pre-wrap;
}
</style>
