<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { PAPER_SIZES, answersDocxUrl, questionsDocxUrl, type ExportListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ExportHeaderFieldsField from '@/components/exports/ExportHeaderFieldsField.vue'
import ExportQuestionsField from '@/components/exports/ExportQuestionsField.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
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
import { collectQuestionPoints, collectTypePoints } from '@/export/scoring'
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
 * 題目與配分 and 表頭欄位 are widgets of their own (`ExportQuestionsField`,
 * `ExportHeaderFieldsField`); what stays here is which part of their state is
 * remembered. The paper size, the 表頭 columns and the per-type defaults are
 * preferences and live in `exportPrefs` (localStorage); the per-question
 * overrides live with the selection itself in `exportSelection`, which prunes
 * them when a question is unticked — as page state they were wiped by a round
 * trip to 題庫 (docs/decisions/2026-08-17-professional-form-pages.md D30).
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

/**
 * The running job in one line. It carries the paper's title, so it is an
 * arbitrarily long string: shown ellipsised with the whole line in the tooltip
 * (docs/frontend.md 清單有界原則).
 */
const jobMeta = computed(() => {
  const entry = store.currentJob
  if (entry === null) {
    return ''
  }
  return t('exports.job.meta', {
    id: entry.jobId,
    title: entry.title,
    paper: paperSizeLabel(entry.paperSize),
    count: entry.questionCount,
    datetime: formatDateTime(entry.submittedAt),
  })
})

/** The failure line, which names the offending question ids — same treatment. */
const jobFailure = computed(() =>
  error.value === null
    ? t('exports.job.failedNoDetail')
    : t('exports.job.failed', { error: error.value }),
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
    ellipsis: true,
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
      questionPoints: collectQuestionPoints(selection.selectedIds, selection.questionPoints),
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
    <PageHeader :page-name="t('nav.exports')">
      <template #actions>
        <AppButton
          variant="secondary"
          icon
          :disabled="store.historyLoading"
          :aria-label="t('exports.history.reload')"
          :title="t('exports.history.reload')"
          @click="store.loadHistory()"
        >
          <AppIcon name="refresh" />
        </AppButton>
      </template>
    </PageHeader>

    <form class="export-form" @submit.prevent="onSubmit">
      <section class="form-section">
        <h2 class="form-section__title">{{ t('exports.questions.section') }}</h2>

        <ExportQuestionsField
          v-model:type-points="prefs.typePoints"
          :rows="selectionRows"
          :types="selectionTypes"
          :loading="selectionLoading"
          :load-error="selectionError"
          :loaded="selectionLoaded"
          @reload="reloadSelection"
        />
      </section>

      <section class="form-section">
        <h2 class="form-section__title">{{ t('exports.form.paperSection') }}</h2>

        <div class="export-form__row">
          <label class="form-field export-form__title-field">
            <span class="form-label">{{ t('exports.form.paperTitle') }}</span>
            <input
              v-model="title"
              class="form-input"
              type="text"
              required
              :placeholder="t('exports.form.paperTitlePlaceholder')"
            />
          </label>

          <label class="form-field export-form__paper-field">
            <span class="form-label">{{ t('exports.form.paperSize') }}</span>
            <select v-model="prefs.paperSize" class="form-select">
              <option v-for="size in PAPER_SIZES" :key="size.name" :value="size.name">
                {{ paperSizeLabel(size.name) }}
              </option>
            </select>
          </label>
        </div>

        <ExportHeaderFieldsField v-model="prefs.headerFields" />
      </section>

      <p v-if="submitError !== null" class="form-error">{{ submitError }}</p>

      <div class="export-form__actions">
        <AppButton type="submit" :disabled="!canSubmit">
          {{ submitting ? t('exports.form.submitting') : t('exports.form.submit') }}
        </AppButton>
      </div>
    </form>

    <section v-if="store.currentJob !== null" class="export-job">
      <div class="export-job__head">
        <StatusBadge v-if="status !== null" :status="status" />
        <span v-else class="muted-text">{{ t('job.progress.notStarted') }}</span>
        <ProgressText v-if="isActive" :progress="progress" />
      </div>

      <p class="export-job__meta text-ellipsis" :title="jobMeta">{{ jobMeta }}</p>

      <p v-if="requestError !== null" class="form-error">{{ requestError }}</p>

      <template v-if="status === 'failed'">
        <p class="form-error text-ellipsis" :title="jobFailure">{{ jobFailure }}</p>
        <div>
          <AppButton
            variant="secondary"
            icon
            :aria-label="t('exports.job.retry')"
            :title="t('exports.job.retry')"
            @click="retry"
          >
            <AppIcon name="refresh" />
          </AppButton>
        </div>
      </template>
    </section>

    <section class="export-history">
      <header class="export-history__head">
        <h2 class="export-history__title">{{ t('exports.history.title') }}</h2>
        <span class="muted-text">
          {{ t('exports.history.count', { count: formatCount(store.history.length) }) }}
        </span>
      </header>

      <p v-if="store.historyError !== null" class="error-banner">
        {{ store.historyError }}
        <AppButton
          variant="secondary"
          icon
          :aria-label="t('exports.history.reload')"
          :title="t('exports.history.reload')"
          @click="store.loadHistory()"
        >
          <AppIcon name="refresh" :size="16" />
        </AppButton>
      </p>

      <DataTable
        :columns="historyColumns"
        :rows="store.history"
        :row-key="(item: ExportListItem) => item.id"
        :loading="store.historyLoading"
        :empty-title="t('exports.history.emptyTitle')"
      >
        <template #downloads="{ row }">
          <div class="export-history__downloads">
            <a v-if="row.questions_available" :href="questionsDocxUrl(row.id)">
              {{ t('exports.history.questions') }}
            </a>
            <span v-else class="export-history__missing" :title="t('exports.history.unavailable')">
              {{ t('exports.history.questions') }}
            </span>

            <a v-if="row.answers_available" :href="answersDocxUrl(row.id)">
              {{ t('exports.history.answers') }}
            </a>
            <span v-else class="export-history__missing" :title="t('exports.history.unavailable')">
              {{ t('exports.history.answers') }}
            </span>
          </div>
        </template>
      </DataTable>
    </section>
  </div>
</template>

<style scoped>
/* Sections split by hairlines, fields sized to their content, and a readable
   line length (docs/decisions/2026-08-17-professional-form-pages.md D27/D28) */
.export-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 44rem;
}

.export-form__row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-4);
}

.export-form__title-field {
  flex: 1 1 20rem;
  min-width: 0;
}

.export-form__paper-field {
  flex: 0 1 15rem;
}

/* The submit row closes the form the way a dialog footer closes a dialog */
.export-form__actions {
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-hairline);
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
  font-variant-numeric: tabular-nums;
}

/* The history is an independent dataset from the selection above it, so it
   bounds its own height and scrolls inside itself instead of adding its rows
   to the page's scroll (docs/frontend.md 設計節制原則 D21). The bound is lower
   than the table's default because this page carries a form above it. */
.export-history {
  --data-table-max-height: max(20rem, calc(100vh - 30rem));

  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.export-history__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-3);
}

/* Names the second dataset on the page; the current job above it is identified
   by its own status line, not by a heading */
.export-history__title {
  font-size: var(--font-size-base);
}

.export-history__downloads {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-4);
}

/* A file that was never produced: same size as its link, struck through and in
   the muted tone, with 「檔案尚未產生」 in its tooltip */
.export-history__missing {
  color: var(--color-text-muted);
  text-decoration: line-through;
}
</style>
