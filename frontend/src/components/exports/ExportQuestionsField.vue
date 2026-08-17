<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type { QuestionType } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import type { SelectedQuestionRow } from '@/composables/useSelectedQuestions'
import { scoredCount, totalPoints } from '@/export/scoring'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import { useExportSelectionStore } from '@/stores/exportSelection'
import ExportQuestionsModal from './ExportQuestionsModal.vue'

/**
 * 題目與配分 on the 匯出 form: a button and one line of summary, nothing else
 * (docs/decisions/2026-08-17-professional-form-pages.md D29).
 *
 * The selection is as long as the paper, so the form shows only how many
 * questions it holds and what they add up to, and keeps the list — with its
 * per-question scores and remove buttons — in the modal: the same
 * 「觸發按鈕＋Modal」 shape the 出題 scope pickers use, and the reason the
 * form's height no longer depends on how many questions were selected
 * (docs/frontend.md 清單有界原則).
 *
 * The one thing that must not hide in the modal is a question that has left
 * the approved bank: it is what would make the export job fail, so its warning
 * line stays on the page.
 */
const props = defineProps<{
  rows: readonly SelectedQuestionRow[]
  types: readonly QuestionType[]
  loading: boolean
  loadError: string | null
  loaded: boolean
}>()

const emit = defineEmits<{ reload: [] }>()

const { t } = useAppI18n()
const selection = useExportSelectionStore()

const modalOpen = ref(false)

/** Only meaningful once a fetch has succeeded; before that nothing is known. */
const hasUnavailable = computed(
  () => props.loaded && props.rows.some((row) => row.question === null),
)

const summary = computed(() => {
  if (selection.count === 0) {
    return t('exports.selection.emptyTitle')
  }
  const parts = [t('exports.selection.count', { count: selection.count })]
  if (props.loading) {
    parts.push(t('exports.selection.loading'))
  } else {
    const withPoints = scoredCount(selection.selectedIds, selection.questionPoints)
    parts.push(
      withPoints === 0
        ? t('exports.scoring.summaryNone')
        : t('exports.scoring.summary', {
            total: formatCount(totalPoints(selection.selectedIds, selection.questionPoints)),
            scored: withPoints,
            count: selection.count,
          }),
    )
  }
  return parts.join(' · ')
})
</script>

<template>
  <div class="questions-field">
    <div class="questions-field__control">
      <AppButton
        variant="secondary"
        size="sm"
        :disabled="selection.count === 0"
        @click="modalOpen = true"
      >
        {{ t('exports.questions.open') }}
      </AppButton>

      <span class="questions-field__summary text-ellipsis" :title="summary">{{ summary }}</span>

      <RouterLink v-if="selection.count === 0" :to="{ name: 'questions' }">
        {{ t('exports.selection.goBank') }}
      </RouterLink>
    </div>

    <p v-if="props.loadError !== null" class="error-banner">
      {{ props.loadError }}
      <AppButton
        variant="secondary"
        icon
        size="sm"
        :aria-label="t('exports.selection.reload')"
        :title="t('exports.selection.reload')"
        @click="emit('reload')"
      >
        <AppIcon name="refresh" :size="16" />
      </AppButton>
    </p>

    <p v-if="hasUnavailable" class="form-error">{{ t('exports.selection.unavailableHint') }}</p>

    <ExportQuestionsModal
      :open="modalOpen"
      :rows="props.rows"
      :types="props.types"
      @close="modalOpen = false"
    />
  </div>
</template>

<style scoped>
.questions-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.questions-field__control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  min-width: 0;
}

.questions-field__summary {
  min-width: 0;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}
</style>
