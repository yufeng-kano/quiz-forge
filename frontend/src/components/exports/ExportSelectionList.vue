<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { listQuestions, type QuestionListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { questionDifficultyLabel, questionTypeLabel } from '@/questions/labels'
import { useExportSelectionStore } from '@/stores/exportSelection'

/**
 * The questions queued for the export, in the order they were picked on 題庫.
 *
 * The selection store holds ids only, so the rows are looked up in the approved
 * question list fetched here — one request rather than one per id, and always
 * the server's current version. An id the list does not contain is a question
 * that has since left the approved range; it is shown as such instead of being
 * dropped silently, because it is exactly what would make the export job fail
 * (docs/export.md — 全部必須 `approved`，否則 job 失敗並列出違規 id).
 */
const { t } = useAppI18n()
const selection = useExportSelectionStore()

const approved = ref<QuestionListItem[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)
const loaded = ref(false)

const byId = computed(() => new Map(approved.value.map((question) => [question.id, question])))

interface SelectionRow {
  id: number
  question: QuestionListItem | null
}

const rows = computed<SelectionRow[]>(() =>
  selection.selectedIds.map((id) => ({ id, question: byId.value.get(id) ?? null })),
)

/** Only meaningful once a fetch has succeeded; before that nothing is known. */
const hasUnavailable = computed(
  () => loaded.value && rows.value.some((row) => row.question === null),
)

async function load(options: { silent?: boolean } = {}): Promise<void> {
  if (!(options.silent ?? false)) {
    loading.value = true
  }
  try {
    approved.value = (await listQuestions({ status: 'approved' })).items
    loaded.value = true
    loadError.value = null
  } catch (error) {
    loadError.value = translateApiError(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})

// Coming back from 題庫 with newly picked questions: refetch so their rows can
// be filled in, without blanking the ones already on screen.
watch(
  () => selection.selectedIds,
  (ids) => {
    if (loaded.value && ids.some((id) => !byId.value.has(id))) {
      void load({ silent: true })
    }
  },
)
</script>

<template>
  <section class="selection">
    <header class="selection__header">
      <h3 class="selection__title">{{ t('exports.selection.title') }}</h3>
      <span class="selection__count">
        {{ t('exports.selection.count', { count: selection.count }) }}
      </span>
      <AppButton variant="secondary" @click="selection.clear()">
        {{ t('exports.selection.clear') }}
      </AppButton>
    </header>

    <p v-if="loading" class="form-hint">{{ t('exports.selection.loading') }}</p>

    <p v-if="loadError !== null" class="selection__error">
      {{ loadError }}
      <AppButton variant="secondary" @click="load()">
        {{ t('exports.selection.reload') }}
      </AppButton>
    </p>

    <ul class="selection__list">
      <li v-for="row in rows" :key="row.id" class="selection__row">
        <span class="selection__id">{{ t('exports.selection.item', { id: row.id }) }}</span>

        <template v-if="row.question !== null">
          <span class="selection__type">{{ questionTypeLabel(row.question.type) }}</span>
          <span class="selection__difficulty">
            {{ questionDifficultyLabel(row.question.difficulty) }}
          </span>
        </template>

        <span v-else-if="loaded" class="selection__unavailable">
          {{ t('exports.selection.unavailable') }}
        </span>

        <button
          type="button"
          class="editor-remove selection__remove"
          @click="selection.deselect(row.id)"
        >
          {{ t('exports.selection.remove') }}
        </button>
      </li>
    </ul>

    <p v-if="hasUnavailable" class="form-error">{{ t('exports.selection.unavailableHint') }}</p>
  </section>
</template>

<style scoped>
.selection {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.selection__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
}

.selection__title {
  font-size: 1rem;
}

.selection__count {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  margin-right: auto;
}

.selection__list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0;
  list-style: none;
}

.selection__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.75rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
}

.selection__id {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
}

.selection__type {
  color: var(--color-heading);
  font-weight: 600;
}

.selection__difficulty {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.selection__unavailable {
  color: var(--color-status-failed-text);
  font-size: 0.875rem;
}

.selection__remove {
  margin-left: auto;
}

.selection__error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-status-failed-border);
  border-radius: 8px;
  background: var(--color-status-failed-bg);
  color: var(--color-status-failed-text);
}
</style>
