<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ExportPoints, QuestionType } from '@/api'
import AppButton from '@/components/AppButton.vue'
import type { SelectedQuestionRow } from '@/composables/useSelectedQuestions'
import {
  scoredCount,
  toScoredQuestions,
  totalPoints,
  type QuestionPointsDraft,
} from '@/export/scoring'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import ExportScoringModal from './ExportScoringModal.vue'

/**
 * 配分 on the 匯出 form: a button and one line of summary, nothing else.
 *
 * The scoring of a paper is as long as its question list, so the form shows
 * only what it adds up to and keeps the editing in a modal — the same
 * 「觸發按鈕＋Modal」 shape the 出題 scope pickers use, and the reason the form's
 * height no longer depends on how many questions were selected
 * (docs/frontend.md 清單有界原則).
 */
const props = defineProps<{
  rows: readonly SelectedQuestionRow[]
  types: readonly QuestionType[]
}>()

const typePoints = defineModel<ExportPoints>('typePoints', { required: true })
const questionPoints = defineModel<QuestionPointsDraft>('questionPoints', { required: true })

const { t } = useAppI18n()

const modalOpen = ref(false)

const scored = computed(() => toScoredQuestions(props.rows))

const summary = computed(() => {
  if (scored.value.length === 0) {
    return t('exports.scoring.summaryEmpty')
  }
  const withPoints = scoredCount(scored.value, typePoints.value, questionPoints.value)
  if (withPoints === 0) {
    return t('exports.scoring.summaryNone')
  }
  return t('exports.scoring.summary', {
    total: formatCount(totalPoints(scored.value, typePoints.value, questionPoints.value)),
    scored: withPoints,
    count: scored.value.length,
  })
})
</script>

<template>
  <div class="form-field">
    <span class="form-label">{{ t('exports.scoring.label') }}</span>

    <div class="scoring-field__control">
      <AppButton variant="secondary" size="sm" @click="modalOpen = true">
        {{ t('exports.scoring.open') }}
      </AppButton>
      <span class="scoring-field__summary text-ellipsis" :title="summary">{{ summary }}</span>
    </div>

    <ExportScoringModal
      v-model:type-points="typePoints"
      v-model:question-points="questionPoints"
      :open="modalOpen"
      :rows="props.rows"
      :types="props.types"
      @close="modalOpen = false"
    />
  </div>
</template>

<style scoped>
.scoring-field__control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  min-width: 0;
}

.scoring-field__summary {
  min-width: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}
</style>
