<script setup lang="ts">
import { computed } from 'vue'

import type { FillBlankPayload } from '@/api'
import QuestionAnswerBlock from '@/components/questions/QuestionAnswerBlock.vue'
import { useAppI18n } from '@/i18n'
import { FILL_BLANK_MARKER } from '@/questions/payload'

/**
 * `fill_blank` — docs/question-bank.md 填充題.
 *
 * The stored stem marks blanks with `____`. Splitting on that marker lets each
 * blank be numbered on screen, so the ordered `answers` can be read against the
 * blank they belong to instead of being counted by hand.
 */
const props = defineProps<{ payload: FillBlankPayload }>()

const { t } = useAppI18n()

const segments = computed(() => props.payload.stem.split(FILL_BLANK_MARKER))
</script>

<template>
  <div class="question-body">
    <p class="question-stem">
      <template v-for="(segment, index) in segments" :key="index">
        <span>{{ segment }}</span>
        <span v-if="index < segments.length - 1" class="fill-blank__slot">{{ index + 1 }}</span>
      </template>
    </p>

    <QuestionAnswerBlock :label="t('questions.labels.answers')">
      <ol class="fill-blank__answers">
        <li v-for="(answer, index) in payload.answers" :key="index">
          <span class="fill-blank__answer-label">
            {{ t('questions.fillBlank.blankNo', { no: index + 1 }) }}
          </span>
          {{ answer }}
        </li>
      </ol>
    </QuestionAnswerBlock>
  </div>
</template>

<style scoped>
.fill-blank__slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2.4rem;
  margin: 0 0.2rem;
  padding: 0 0.3rem;
  border-bottom: 1px solid var(--color-accent);
  color: var(--color-accent-strong);
  font-variant-numeric: tabular-nums;
}

.fill-blank__answers {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0;
  list-style: none;
}

.fill-blank__answer-label {
  margin-right: 0.4rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}
</style>
