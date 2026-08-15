<script setup lang="ts">
import { computed } from 'vue'

import type { AnalogyPayload } from '@/api'
import QuestionAnswerBlock from '@/components/questions/QuestionAnswerBlock.vue'
import QuestionOptionList from '@/components/questions/QuestionOptionList.vue'
import { useAppI18n } from '@/i18n'

/**
 * `analogy` — docs/question-bank.md 類比題.
 *
 * The stem is never stored: it is composed from the a/b/c slots here so every
 * analogy question reads identically. With `options` the question is a single
 * choice, without them it is a blank to fill in.
 */
const props = defineProps<{ payload: AnalogyPayload }>()

const { t } = useAppI18n()

const stem = computed(() =>
  t('questions.analogy.stem', {
    a: props.payload.a,
    b: props.payload.b,
    c: props.payload.c,
  }),
)

/** Where the stored answer sits in the option list, or null when it is absent. */
const answerIndex = computed(() => {
  const options = props.payload.options
  if (options === null) {
    return null
  }
  const index = options.indexOf(props.payload.answer)
  return index === -1 ? null : index
})
</script>

<template>
  <div class="question-body">
    <p class="question-stem">{{ stem }}</p>

    <QuestionOptionList
      v-if="payload.options !== null"
      :options="payload.options"
      :answer-index="answerIndex"
    />
    <p v-else class="form-hint">{{ t('questions.analogy.fillForm') }}</p>

    <QuestionAnswerBlock :label="t('questions.labels.answer')">
      {{ payload.answer }}
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
