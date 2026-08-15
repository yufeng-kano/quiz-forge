<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'
import type { SelectedQuestionRow } from '@/composables/useSelectedQuestions'
import { useAppI18n } from '@/i18n'
import { questionDifficultyLabel, questionTypeLabel } from '@/questions/labels'
import { useExportSelectionStore } from '@/stores/exportSelection'

/**
 * The questions queued for the export, in the order they were picked on 題庫.
 *
 * The rows are resolved by the page (`useSelectedQuestions`), which is also
 * what the 每題型配分 fields are built from — one lookup feeds both instead of
 * this component fetching a second copy. A row whose question could not be
 * found is shown as such rather than dropped silently: it is what would make
 * the export job fail (docs/export.md — 全部必須 `approved`，否則 job 失敗並
 * 列出違規 id).
 */
const props = defineProps<{
  rows: readonly SelectedQuestionRow[]
  loading: boolean
  loadError: string | null
  loaded: boolean
}>()

const emit = defineEmits<{ reload: [] }>()

const { t } = useAppI18n()
const selection = useExportSelectionStore()

/** Only meaningful once a fetch has succeeded; before that nothing is known. */
const hasUnavailable = computed(
  () => props.loaded && props.rows.some((row) => row.question === null),
)
</script>

<template>
  <section class="card selection">
    <header class="selection__header">
      <h2 class="card-title">{{ t('exports.selection.title') }}</h2>
      <span class="selection__count">
        {{ t('exports.selection.count', { count: selection.count }) }}
      </span>
      <AppButton variant="secondary" size="sm" @click="selection.clear()">
        {{ t('exports.selection.clear') }}
      </AppButton>
    </header>

    <p v-if="props.loading" class="form-hint">{{ t('exports.selection.loading') }}</p>

    <p v-if="props.loadError !== null" class="error-banner">
      {{ props.loadError }}
      <AppButton variant="secondary" size="sm" @click="emit('reload')">
        {{ t('exports.selection.reload') }}
      </AppButton>
    </p>

    <ul class="selection__list">
      <li v-for="row in props.rows" :key="row.id" class="selection__row">
        <span class="selection__id">{{ t('exports.selection.item', { id: row.id }) }}</span>

        <template v-if="row.question !== null">
          <span class="selection__type">{{ questionTypeLabel(row.question.type) }}</span>
          <span class="selection__difficulty">
            {{ questionDifficultyLabel(row.question.difficulty) }}
          </span>
        </template>

        <span v-else-if="props.loaded" class="selection__unavailable">
          {{ t('exports.selection.unavailable') }}
        </span>

        <AppButton
          variant="ghost"
          size="sm"
          class="selection__remove"
          @click="selection.deselect(row.id)"
        >
          {{ t('exports.selection.remove') }}
        </AppButton>
      </li>
    </ul>

    <p v-if="hasUnavailable" class="form-error">{{ t('exports.selection.unavailableHint') }}</p>
  </section>
</template>

<style scoped>
.selection {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.selection__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.selection__count {
  margin-right: auto;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

.selection__list {
  display: flex;
  flex-direction: column;
  padding: 0;
  list-style: none;
}

.selection__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1) var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.selection__row:last-child {
  border-bottom: none;
}

.selection__id {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

.selection__type {
  color: var(--color-heading);
  font-weight: 600;
}

.selection__difficulty {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.selection__unavailable {
  color: var(--color-status-failed-text);
  font-size: var(--font-size-md);
}

.selection__remove {
  margin-left: auto;
}
</style>
