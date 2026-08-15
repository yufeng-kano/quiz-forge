<script setup lang="ts">
import type { TrueFalsePayload } from '@/api'
import QuestionAnswerBlock from '@/components/questions/QuestionAnswerBlock.vue'
import { useAppI18n } from '@/i18n'

/** `true_false` — docs/question-bank.md 是非題. */
defineProps<{ payload: TrueFalsePayload }>()

const { t } = useAppI18n()
</script>

<template>
  <div class="question-body">
    <p class="question-stem">{{ payload.stem }}</p>

    <QuestionAnswerBlock :label="t('questions.labels.answer')">
      {{ payload.answer ? t('questions.trueFalse.true') : t('questions.trueFalse.false') }}
    </QuestionAnswerBlock>

    <QuestionAnswerBlock
      v-if="payload.explanation !== null && payload.explanation !== ''"
      :label="t('questions.labels.explanation')"
      variant="explanation"
    >
      {{ payload.explanation }}
    </QuestionAnswerBlock>
  </div>
</template>
