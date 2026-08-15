<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type { DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { useToastsStore } from '@/stores/toasts'

/**
 * Actions of one document row: open, rename, move to a folder, retry the
 * failed parse job, delete.
 *
 * Everything that opens a dialog is raised to the list view (`rename`, `move`,
 * `delete`), which owns those dialogs and the store calls; retrying is handled
 * here because it needs this row's own job subscription. Subscribing twice per
 * row (here and in the status cell) costs no extra request — `stores/jobs.ts`
 * shares one timer per job id between all its subscribers.
 *
 * 移至資料夾 is deliberately present even though a row can be dragged onto the
 * folder column: dragging must not be the only way to file a document.
 */
const props = withDefaults(
  defineProps<{
    document: DocumentListItem
    jobId: number | null
    /**
     * Show 改名 and 移至資料夾. Only the 文件庫 table sets it: the 上傳 tab's
     * list is about the parse that is still running, not about organising the
     * library.
     */
    organizable?: boolean
  }>(),
  { organizable: false },
)

const emit = defineEmits<{
  rename: [document: DocumentListItem]
  move: [document: DocumentListItem]
  delete: [document: DocumentListItem]
}>()

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

    <AppButton
      v-if="props.organizable"
      variant="ghost"
      size="sm"
      @click="emit('rename', props.document)"
    >
      {{ t('documents.row.rename') }}
    </AppButton>

    <AppButton
      v-if="props.organizable"
      variant="ghost"
      size="sm"
      @click="emit('move', props.document)"
    >
      {{ t('documents.folders.moveAction') }}
    </AppButton>

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
