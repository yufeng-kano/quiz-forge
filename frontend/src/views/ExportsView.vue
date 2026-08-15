<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { DEFAULT_PAPER_SIZE, PAPER_SIZES, type PaperSize } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ExportHistoryRow from '@/components/exports/ExportHistoryRow.vue'
import ExportSelectionList from '@/components/exports/ExportSelectionList.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { paperSizeLabel } from '@/export/labels'
import { useExportSelectionStore } from '@/stores/exportSelection'
import { useExportsStore } from '@/stores/exports'

/**
 * 匯出 — turn the 題庫 selection into a pair of Word files (docs/export.md).
 *
 * The page is the second half of the selection flow: what was ticked on
 * `/questions` is listed here, a paper size is chosen, and `POST
 * /api/v1/exports` queues the rendering job whose progress (`3/4`, one step per
 * question) is polled below. When it finishes the history is refetched — that
 * is where the download links live — and the selection is emptied, since those
 * questions are now on a paper. A failed job keeps the selection: its `error`
 * names the ids to fix, and nothing else could be done about it here.
 */
const { t } = useAppI18n()
const selection = useExportSelectionStore()
const store = useExportsStore()

const paperSize = ref<PaperSize>(DEFAULT_PAPER_SIZE)
const submitting = ref(false)
const submitError = ref<string | null>(null)

const { status, progress, error, requestError, isActive, retry } = useJobPolling(
  () => store.currentJob?.jobId ?? null,
)

/** A second paper cannot be queued while the previous one is still rendering. */
const canSubmit = computed(() => selection.count > 0 && !submitting.value && !isActive.value)

onMounted(async () => {
  await store.loadHistory({ silent: store.historyLoaded })
})

/**
 * `immediate` matters: the job may already be `done` in the jobs store when the
 * page is mounted again, in which case `status` never transitions here. The
 * `settled` flag is what keeps the follow-up from running twice.
 */
watch(
  status,
  (current) => {
    const entry = store.currentJob
    if (current !== 'done' || entry === null || entry.settled) {
      return
    }
    store.markCurrentJobSettled()
    selection.clear()
    void store.loadHistory({ silent: true })
  },
  { immediate: true },
)

async function onSubmit(): Promise<void> {
  if (!canSubmit.value) {
    return
  }
  submitting.value = true
  submitError.value = null
  try {
    await store.submit(selection.selectedIds, paperSize.value)
  } catch (caught) {
    submitError.value = translateApiError(caught)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h2 class="page-title">{{ t('pages.exports.title') }}</h2>
      <p class="page-description">{{ t('pages.exports.description') }}</p>
    </header>

    <ExportSelectionList v-if="selection.count > 0" />

    <EmptyState
      v-else
      :title="t('exports.selection.emptyTitle')"
      :description="t('exports.selection.emptyDescription')"
    >
      <template #actions>
        <RouterLink class="exports__link" :to="{ name: 'questions' }">
          {{ t('exports.selection.goBank') }}
        </RouterLink>
      </template>
    </EmptyState>

    <form class="export-form" @submit.prevent="onSubmit">
      <h3 class="export-form__title">{{ t('exports.form.title') }}</h3>

      <label class="form-field export-form__field">
        <span class="form-label">{{ t('exports.form.paperSize') }}</span>
        <select v-model="paperSize" class="form-select">
          <option v-for="size in PAPER_SIZES" :key="size.name" :value="size.name">
            {{ paperSizeLabel(size.name) }}
          </option>
        </select>
        <span class="form-hint">{{ t('exports.form.paperHint') }}</span>
      </label>

      <p v-if="submitError !== null" class="form-error">{{ submitError }}</p>

      <div>
        <AppButton type="submit" :disabled="!canSubmit">
          {{ submitting ? t('exports.form.submitting') : t('exports.form.submit') }}
        </AppButton>
      </div>
    </form>

    <section v-if="store.currentJob !== null" class="export-job">
      <div class="export-job__head">
        <h3 class="export-job__title">{{ t('exports.job.title') }}</h3>
        <StatusBadge v-if="status !== null" :status="status" />
        <ProgressText v-if="isActive" :progress="progress" />
      </div>

      <p class="export-job__meta">
        {{
          t('exports.job.meta', {
            id: store.currentJob.jobId,
            paper: paperSizeLabel(store.currentJob.paperSize),
            count: store.currentJob.questionCount,
            datetime: formatDateTime(store.currentJob.submittedAt),
          })
        }}
      </p>

      <p v-if="requestError !== null" class="form-error">{{ requestError }}</p>

      <template v-if="status === 'failed'">
        <p class="form-error">
          {{
            error === null ? t('exports.job.failedNoDetail') : t('exports.job.failed', { error })
          }}
        </p>
        <div>
          <AppButton variant="secondary" @click="retry">{{ t('exports.job.retry') }}</AppButton>
        </div>
      </template>

      <p v-else-if="status === 'done'" class="export-job__done">{{ t('exports.job.done') }}</p>

      <p v-else-if="status === null" class="form-hint">{{ t('job.progress.notStarted') }}</p>
    </section>

    <section class="export-history">
      <h3 class="export-history__title">{{ t('exports.history.title') }}</h3>

      <p v-if="store.historyError !== null" class="export-history__error">
        {{ store.historyError }}
        <AppButton variant="secondary" @click="store.loadHistory()">
          {{ t('exports.history.reload') }}
        </AppButton>
      </p>

      <p v-if="store.historyLoading" class="form-hint">{{ t('exports.history.loading') }}</p>

      <template v-else-if="store.history.length > 0">
        <p class="form-hint">{{ t('exports.history.count', { count: store.history.length }) }}</p>
        <ul class="export-history__list">
          <li v-for="item in store.history" :key="item.id">
            <ExportHistoryRow :item="item" />
          </li>
        </ul>
      </template>

      <EmptyState
        v-else-if="store.historyLoaded"
        :title="t('exports.history.emptyTitle')"
        :description="t('exports.history.emptyDescription')"
      />
    </section>
  </section>
</template>

<style scoped>
.exports__link {
  color: var(--color-accent);
}

.export-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background-soft);
}

.export-form__title {
  font-size: 1rem;
}

.export-form__field {
  max-width: 22rem;
}

.export-job {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

.export-job__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
}

.export-job__title {
  font-size: 1rem;
}

.export-job__meta {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
}

.export-job__done {
  color: var(--color-status-done-text);
}

.export-history {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.export-history__title {
  font-size: 1rem;
}

.export-history__list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0;
  list-style: none;
}

.export-history__error {
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
