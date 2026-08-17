<script setup lang="ts">
import { computed, ref } from 'vue'

import type { DocumentListItem } from '@/api'
import AppMenu from '@/components/ui/AppMenu.vue'
import AppMenuItem from '@/components/ui/AppMenuItem.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { useToastsStore } from '@/stores/toasts'

/**
 * Actions of one document row, behind a single overflow trigger.
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
const props = defineProps<{
  document: DocumentListItem
  jobId: number | null
}>()

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
  <AppMenu :label="t('documents.row.moreActions')">
    <AppMenuItem :to="{ name: 'document-detail', params: { id: String(props.document.id) } }">
      {{ t('documents.row.open') }}
    </AppMenuItem>
    <AppMenuItem @select="emit('rename', props.document)">
      {{ t('documents.row.rename') }}
    </AppMenuItem>
    <AppMenuItem @select="emit('move', props.document)">
      {{ t('documents.folders.moveAction') }}
    </AppMenuItem>
    <AppMenuItem v-if="canRetry" :disabled="retrying" @select="onRetry">
      {{ retrying ? t('documents.row.retrying') : t('documents.row.retryJob') }}
    </AppMenuItem>
    <AppMenuItem danger @select="emit('delete', props.document)">
      {{ t('documents.row.delete') }}
    </AppMenuItem>
  </AppMenu>
</template>
