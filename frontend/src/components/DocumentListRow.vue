<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import type { DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'

/**
 * One row of the document list.
 *
 * The row owns its own job subscription: `useJobPolling` is per component
 * instance, so making the row a component is what lets several documents parse
 * at once, each showing its own progress. When the job settles, the row
 * refetches itself so the status, title and page count come from the server
 * rather than being guessed from the job.
 */
const props = defineProps<{
  document: DocumentListItem
  /** `parse_document` job id, when this session created the document. */
  jobId: number | null
}>()

const { t } = useAppI18n()
const router = useRouter()
const store = useDocumentsStore()

const {
  status: jobStatus,
  progress,
  error: jobError,
  requestError: jobRequestError,
  isActive,
  retry,
} = useJobPolling(() => props.jobId)

const confirmingDelete = ref(false)
const deleting = ref(false)
const retryingJob = ref(false)
const actionError = ref<string | null>(null)

const jobFailed = computed(() => jobStatus.value === 'failed')

const jobFailureText = computed(() => {
  if (!jobFailed.value) {
    return null
  }
  const reason = jobError.value
  return reason === null || reason.trim() === ''
    ? t('documents.row.jobFailedNoDetail')
    : t('documents.row.jobFailed', { error: reason })
})

const detailRoute = computed(() => ({
  name: 'document-detail' as const,
  params: { id: String(props.document.id) },
}))

/** Refetch the row once its job stops running. */
watch(isActive, async (active, wasActive) => {
  if (wasActive === true && !active) {
    try {
      await store.refreshDocument(props.document.id)
    } catch (error) {
      actionError.value = translateApiError(error)
    }
  }
})

function openDetail(event: MouseEvent): void {
  // Buttons and links inside the row handle their own clicks.
  if (event.target instanceof Element && event.target.closest('a, button, input') !== null) {
    return
  }
  void router.push(detailRoute.value)
}

async function onRetryJob(): Promise<void> {
  retryingJob.value = true
  actionError.value = null
  try {
    await retry()
  } finally {
    retryingJob.value = false
  }
}

async function onDelete(): Promise<void> {
  deleting.value = true
  actionError.value = null
  try {
    await store.remove(props.document.id)
  } catch (error) {
    actionError.value = translateApiError(error)
    deleting.value = false
    confirmingDelete.value = false
  }
}
</script>

<template>
  <li class="document-row" @click="openDetail">
    <div class="document-row__head">
      <RouterLink class="document-row__title" :to="detailRoute">
        {{ props.document.title }}
      </RouterLink>
      <StatusBadge :status="props.document.status" />
    </div>

    <p class="document-row__meta">
      <span>{{ t(`documents.sourceType.${props.document.source_type}`) }}</span>
      <span>{{ t('documents.row.pageCount', { count: props.document.page_count }) }}</span>
      <span>{{ formatDateTime(props.document.created_at) }}</span>
    </p>

    <p v-if="isActive" class="document-row__progress">
      <ProgressText :progress="progress" />
    </p>

    <p v-if="jobFailureText !== null" class="document-row__error">{{ jobFailureText }}</p>
    <p v-if="jobRequestError !== null" class="document-row__error">{{ jobRequestError }}</p>
    <p v-if="actionError !== null" class="document-row__error">{{ actionError }}</p>

    <div class="document-row__actions">
      <template v-if="confirmingDelete">
        <span class="document-row__confirm">{{ t('documents.row.deleteConfirmQuestion') }}</span>
        <AppButton variant="secondary" :disabled="deleting" @click="confirmingDelete = false">
          {{ t('documents.row.deleteCancel') }}
        </AppButton>
        <AppButton :disabled="deleting" @click="onDelete">
          {{ deleting ? t('documents.row.deleting') : t('documents.row.deleteConfirm') }}
        </AppButton>
      </template>
      <template v-else>
        <AppButton v-if="jobFailed" variant="secondary" :disabled="retryingJob" @click="onRetryJob">
          {{ retryingJob ? t('documents.row.retrying') : t('documents.row.retryJob') }}
        </AppButton>
        <AppButton variant="secondary" @click="confirmingDelete = true">
          {{ t('documents.row.delete') }}
        </AppButton>
      </template>
    </div>
  </li>
</template>

<style scoped>
.document-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.9rem 1.1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
  cursor: pointer;
}

.document-row:hover {
  border-color: var(--color-border-hover);
  background: var(--color-background-soft);
}

.document-row__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.document-row__title {
  color: var(--color-heading);
  font-weight: 600;
  overflow-wrap: anywhere;
}

.document-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 1rem;
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.document-row__progress {
  font-size: 0.875rem;
}

.document-row__error {
  color: var(--color-status-failed-text);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}

.document-row__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.2rem;
}

.document-row__confirm {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}
</style>
