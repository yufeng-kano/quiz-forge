<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type { DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { useToastsStore } from '@/stores/toasts'

/**
 * Actions of one document row: open, retry the failed parse job, delete.
 *
 * Deleting is raised to the list view (`delete` event), which owns the
 * confirmation dialog and the store call; retrying is handled here because it
 * needs this row's own job subscription. Subscribing twice per row (here and
 * in the status cell) costs no extra request — `stores/jobs.ts` shares one
 * timer per job id between all its subscribers.
 */
const props = defineProps<{
  document: DocumentListItem
  jobId: number | null
}>()

const emit = defineEmits<{ delete: [document: DocumentListItem] }>()

const { t } = useAppI18n()
const toasts = useToastsStore()

const { status: jobStatus, requestError, retry } = useJobPolling(() => props.jobId)

const canRetry = computed(() => jobStatus.value === 'failed')
const retrying = ref(false)

/**
 * `retry()` records a failed request in the jobs store rather than throwing
 * (a transient error must not kill the polling loop), so the outcome is read
 * back from `requestError` to decide which toast to raise.
 */
async function onRetry(): Promise<void> {
  retrying.value = true
  try {
    await retry()
    const failure = requestError.value
    if (failure === null) {
      toasts.success(t('documents.row.retryQueued', { title: props.document.title }))
    } else {
      toasts.error(failure)
    }
  } finally {
    retrying.value = false
  }
}
</script>

<template>
  <div class="row-actions">
    <RouterLink
      class="row-actions__open"
      :to="{ name: 'document-detail', params: { id: String(props.document.id) } }"
    >
      {{ t('documents.row.open') }}
    </RouterLink>

    <AppButton v-if="canRetry" variant="secondary" size="sm" :disabled="retrying" @click="onRetry">
      {{ retrying ? t('documents.row.retrying') : t('documents.row.retryJob') }}
    </AppButton>

    <AppButton variant="ghost" size="sm" @click="emit('delete', props.document)">
      {{ t('documents.row.delete') }}
    </AppButton>
  </div>
</template>

<style scoped>
.row-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}

.row-actions__open {
  font-size: var(--font-size-md);
}
</style>
