<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { PAPER_SIZES, answersDocxUrl, questionsDocxUrl, type ExportListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ExportHeaderFieldsField from '@/components/exports/ExportHeaderFieldsField.vue'
import ExportScoringField from '@/components/exports/ExportScoringField.vue'
import ExportSelectionList from '@/components/exports/ExportSelectionList.vue'
import DataTable from '@/components/ui/DataTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DataTableColumn } from '@/components/ui/dataTable'
import { useJobPolling } from '@/composables/useJobPolling'
import { useSelectedQuestions } from '@/composables/useSelectedQuestions'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { paperSizeLabel } from '@/export/labels'
import {
  collectQuestionPoints,
  collectTypePoints,
  pruneQuestionPoints,
  type QuestionPointsDraft,
} from '@/export/scoring'
import { useExportPrefsStore } from '@/stores/exportPrefs'
import { useExportSelectionStore } from '@/stores/exportSelection'
import { useExportsStore } from '@/stores/exports'
import { useToastsStore } from '@/stores/toasts'

/**
 * 匯出 — turn the 題庫 selection into a pair of Word files (docs/export.md).
 *
 * The page is the second half of the selection flow: what was ticked on
 * `/questions` is listed here, a title and a paper size are chosen, and
 * `POST /api/v1/exports` queues the rendering job whose progress (`3/4`, one
 * step per question) is polled below. When it finishes the history is
 * refetched — that is where the download links live — and the selection is
 * emptied, since those questions are now on a paper. A failed job keeps the
 * selection: its `error` names the ids to fix, and nothing else could be done
 * about it here.
 *
 * 配分 and 表頭欄位 are widgets of their own (`ExportScoringField`,
 * `ExportHeaderFieldsField`); what stays here is which part of their state is
 * remembered. The paper size, the 表頭 columns and the per-type defaults are
 * preferences and live in `exportPrefs` (localStorage); the per-question
 * overrides describe this one paper and stay in the page, pruned to the
 * selection so a question removed after being scored cannot leave a key the
 * backend would reject.
 */
const { t } = useAppI18n()
const selection = useExportSelectionStore()
const prefs = useExportPrefsStore()
const store = useExportsStore()
const toasts = useToastsStore()

const {
  rows: selectionRows,
  types: selectionTypes,
  loading: selectionLoading,
  loadError: selectionError,
  loaded: selectionLoaded,
  reload: reloadSelection,
} = useSelectedQuestions()

const title = ref('')
/** Per-question point overrides for this paper, keyed by question id. */
const questionPoints = ref<QuestionPointsDraft>({})
const submitting = ref(false)
const submitError = ref<string | null>(null)

const { status, progress, error, requestError, isActive, retry } = useJobPolling(
  () => store.currentJob?.jobId ?? null,
)

const trimmedTitle = computed(() => title.value.trim())

/** A second paper cannot be queued while the previous one is still rendering. */
const canSubmit = computed(
  () => selection.count > 0 && trimmedTitle.value !== '' && !submitting.value && !isActive.value,
)

// An override for a question that has since been unticked would be a key
// outside `question_ids`, which the backend answers with 422; dropping it as
// soon as the selection changes also keeps the modal's total honest.
watch(
  () => selection.selectedIds,
  (ids) => {
    const kept = pruneQuestionPoints(ids, questionPoints.value)
    if (Object.keys(kept).length !== Object.keys(questionPoints.value).length) {
      questionPoints.value = kept
    }
  },
)

const historyColumns = computed<DataTableColumn<ExportListItem>[]>(() => [
  {
    key: 'id',
    label: t('exports.history.columns.id'),
    value: (item) => `#${item.id}`,
    sortValue: (item) => item.id,
    width: '5.5rem',
    nowrap: true,
  },
  {
    key: 'title',
    label: t('exports.history.columns.title'),
    value: (item) => item.title,
    sortValue: (item) => item.title,
  },
  {
    key: 'paper_size',
    label: t('exports.history.columns.paperSize'),
    value: (item) => paperSizeLabel(item.paper_size),
    sortValue: (item) => item.paper_size,
    nowrap: true,
    width: '12rem',
  },
  {
    key: 'question_count',
    label: t('exports.history.columns.questionCount'),
    value: (item) => t('exports.history.questionCount', { count: item.question_count }),
    sortValue: (item) => item.question_count,
    align: 'end',
    width: '7rem',
    nowrap: true,
  },
  {
    key: 'created_at',
    label: t('exports.history.columns.createdAt'),
    value: (item) => formatDateTime(item.created_at),
    sortValue: (item) => item.created_at,
    width: '11rem',
    nowrap: true,
  },
  {
    key: 'downloads',
    label: t('exports.history.columns.downloads'),
    width: '15rem',
    nowrap: true,
  },
])

onMounted(async () => {
  await store.loadHistory({ silent: store.historyLoaded })
})

/**
 * `immediate` matters: the job may already be `done` in the jobs store when the
 * page is mounted again, in which case `status` never transitions here. The
 * `settled` flag is what keeps the follow-up from running twice.
 */
/**
 * Which job a failure toast has already been raised for. A failed job is not
 * marked as settled — it can be retried into a `done` one, and that run still
 * has to clear the selection and refresh the history — so the toast needs its
 * own guard against firing again on every poll.
 */
const failureNotifiedJobId = ref<number | null>(null)

watch(
  status,
  (current) => {
    const entry = store.currentJob
    if (entry === null) {
      return
    }
    if (current === 'done' && !entry.settled) {
      store.markCurrentJobSettled()
      selection.clear()
      toasts.success(t('exports.job.doneToast', { title: entry.title }))
      void store.loadHistory({ silent: true })
      return
    }
    if (current === 'failed' && failureNotifiedJobId.value !== entry.jobId) {
      failureNotifiedJobId.value = entry.jobId
      toasts.error(t('exports.job.failedToast', { title: entry.title }))
    }
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
    const jobId = await store.submit(selection.selectedIds, {
      title: trimmedTitle.value,
      paperSize: prefs.paperSize,
      points: collectTypePoints(selectionTypes.value, prefs.typePoints),
      questionPoints: collectQuestionPoints(selection.selectedIds, questionPoints.value),
      headerFields: prefs.headerFields,
    })
    toasts.success(t('exports.form.queued', { id: jobId }))
  } catch (caught) {
    const message = translateApiError(caught)
    submitError.value = message
    toasts.error(message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <PageHeader :title="t('pages.exports.title')">
      <template #actions>
        <AppButton
          variant="secondary"
          :disabled="store.historyLoading"
          @click="store.loadHistory()"
        >
          {{ t('exports.history.reload') }}
        </AppButton>
      </template>
    </PageHeader>

    <ExportSelectionList
      v-if="selection.count > 0"
      :rows="selectionRows"
      :loading="selectionLoading"
      :load-error="selectionError"
      :loaded="selectionLoaded"
      @reload="reloadSelection"
    />

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

    <form class="card export-form" @submit.prevent="onSubmit">
      <h2 class="card-title">{{ t('exports.form.title') }}</h2>

      <div class="export-form__fields">
        <label class="form-field export-form__title-field">
          <span class="form-label">{{ t('exports.form.paperTitle') }}</span>
          <input
            v-model="title"
            class="form-input"
            type="text"
            required
            :placeholder="t('exports.form.paperTitlePlaceholder')"
          />
          <span class="form-hint">{{ t('exports.form.paperTitleHint') }}</span>
        </label>

        <label class="form-field">
          <span class="form-label">{{ t('exports.form.paperSize') }}</span>
          <select v-model="prefs.paperSize" class="form-select">
            <option v-for="size in PAPER_SIZES" :key="size.name" :value="size.name">
              {{ paperSizeLabel(size.name) }}
            </option>
          </select>
          <span class="form-hint">{{ t('exports.form.paperHint') }}</span>
        </label>

        <ExportScoringField
          v-model:type-points="prefs.typePoints"
          v-model:question-points="questionPoints"
          :rows="selectionRows"
          :types="selectionTypes"
        />

        <ExportHeaderFieldsField v-model="prefs.headerFields" />
      </div>

      <p v-if="submitError !== null" class="form-error">{{ submitError }}</p>

      <div>
        <AppButton type="submit" :disabled="!canSubmit">
          {{ submitting ? t('exports.form.submitting') : t('exports.form.submit') }}
        </AppButton>
      </div>
    </form>

    <section v-if="store.currentJob !== null" class="card export-job">
      <div class="export-job__head">
        <h2 class="card-title">{{ t('exports.job.title') }}</h2>
        <StatusBadge v-if="status !== null" :status="status" />
        <ProgressText v-if="isActive" :progress="progress" />
      </div>

      <p class="export-job__meta">
        {{
          t('exports.job.meta', {
            id: store.currentJob.jobId,
            title: store.currentJob.title,
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
      <header class="export-history__head">
        <h2 class="card-title">{{ t('exports.history.title') }}</h2>
        <span class="muted-text">
          {{ t('exports.history.count', { count: formatCount(store.history.length) }) }}
        </span>
      </header>

      <p v-if="store.historyError !== null" class="error-banner">
        {{ store.historyError }}
        <AppButton variant="secondary" @click="store.loadHistory()">
          {{ t('exports.history.reload') }}
        </AppButton>
      </p>

      <DataTable
        :columns="historyColumns"
        :rows="store.history"
        :row-key="(item: ExportListItem) => item.id"
        :loading="store.historyLoading"
        :empty-title="t('exports.history.emptyTitle')"
        :empty-description="t('exports.history.emptyDescription')"
      >
        <template #downloads="{ row }">
          <div class="export-history__downloads">
            <a v-if="row.questions_available" :href="questionsDocxUrl(row.id)">
              {{ t('exports.history.questions') }}
            </a>
            <span v-else class="export-history__missing" aria-disabled="true">
              {{ t('exports.history.questions') }}
            </span>

            <a v-if="row.answers_available" :href="answersDocxUrl(row.id)">
              {{ t('exports.history.answers') }}
            </a>
            <span v-else class="export-history__missing" aria-disabled="true">
              {{ t('exports.history.answers') }}
            </span>
          </div>
          <p
            v-if="!row.questions_available || !row.answers_available"
            class="export-history__unavailable"
          >
            {{ t('exports.history.unavailable') }}
          </p>
        </template>
      </DataTable>
    </section>
  </div>
</template>

<style scoped>
.exports__link {
  color: var(--color-accent);
}

.export-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.export-form__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: var(--space-3) var(--space-4);
}

.export-form__title-field {
  grid-column: span 2;
  min-width: 0;
}

@media (max-width: 720px) {
  .export-form__title-field {
    grid-column: auto;
  }
}

.export-job {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.export-job__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.export-job__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.export-job__done {
  color: var(--color-status-done-text);
}

.export-history {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.export-history__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.export-history__downloads {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-4);
}

.export-history__missing {
  color: var(--color-text-faint);
  text-decoration: line-through;
}

.export-history__unavailable {
  margin-top: var(--space-1);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}
</style>
