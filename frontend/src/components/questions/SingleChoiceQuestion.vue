<script setup lang="ts">
import { computed } from 'vue'

import type { SingleChoicePayload } from '@/api'
import QuestionAnswerBlock from '@/components/questions/QuestionAnswerBlock.vue'
import QuestionOptionList from '@/components/questions/QuestionOptionList.vue'
import { useAppI18n } from '@/i18n'
import { optionLetter } from '@/questions/options'

/** `single_choice` — docs/question-bank.md 單選題. */
const props = defineProps<{ payload: SingleChoicePayload }>()

const { t } = useAppI18n()

const answerText = computed(() => {
  const option = props.payload.options[props.payload.answer_index]
  if (option === undefined) {
    return String(props.payload.answer_index)
  }
  return `${t('questions.option.marker', { letter: optionLetter(props.payload.answer_index) })} ${option}`
})
</script>

<template>
  <div class="question-body">
    <p class="question-stem">{{ payload.stem }}</p>

    <QuestionOptionList :options="payload.options" :answer-index="payload.answer_index" />

    <QuestionAnswerBlock :label="t('questions.labels.answer')">
      {{ answerText }}
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
