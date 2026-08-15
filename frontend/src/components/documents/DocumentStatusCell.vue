<script setup lang="ts">
import { computed, watch } from 'vue'

import type { DocumentListItem } from '@/api'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { useDocumentsStore } from '@/stores/documents'
import { useToastsStore } from '@/stores/toasts'

/**
 * Status cell of one document row: the document's own status, plus the live
 * progress or failure reason of the `parse_document` job this session started.
 *
 * The subscription belongs to the row rather than the table, which is what
 * lets several documents parse at once, each showing its own progress. When
 * the job settles, the row is refetched so status, title and page count come
 * from the server instead of being guessed from the job.
 */
const props = defineProps<{
  document: DocumentListItem
  /** `parse_document` job id, when this session created the document. */
  jobId: number | null
}>()

const { t } = useAppI18n()
const store = useDocumentsStore()
const toasts = useToastsStore()

const {
  status: jobStatus,
  progress,
  error: jobError,
  requestError,
  isActive,
} = useJobPolling(() => props.jobId)

const failureText = computed(() => {
  if (jobStatus.value !== 'failed') {
    return null
  }
  const reason = jobError.value
  return reason === null || reason.trim() === ''
    ? t('documents.row.jobFailedNoDetail')
    : t('documents.row.jobFailed', { error: reason })
})

watch(isActive, async (active, wasActive) => {
  if (wasActive !== true || active) {
    return
  }
  try {
    await store.refreshDocument(props.document.id)
  } catch {
    // The row keeps its last known state; the list's own polling will catch up.
    toasts.error(t('documents.row.refreshFailed', { title: props.document.title }))
  }
})
</script>

<template>
  <div class="status-cell">
    <StatusBadge :status="props.document.status" />
    <ProgressText v-if="isActive" :progress="progress" />
    <p v-if="failureText !== null" class="status-cell__error">{{ failureText }}</p>
    <p v-if="requestError !== null" class="status-cell__error">{{ requestError }}</p>
  </div>
</template>

<style scoped>
.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.status-cell__error {
  color: var(--color-status-failed-text);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}
</style>
