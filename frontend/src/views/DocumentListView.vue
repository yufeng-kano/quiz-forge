<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'

import { DOCUMENT_POLL_INTERVAL_MS } from '@/api'
import AppButton from '@/components/AppButton.vue'
import DocumentIntakePanel from '@/components/DocumentIntakePanel.vue'
import DocumentListRow from '@/components/DocumentListRow.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useAppI18n } from '@/i18n'
import { useDocumentsStore } from '@/stores/documents'

/**
 * Document list plus the upload / URL-import entry points.
 *
 * Rows created in this session carry a job id and refresh themselves through
 * `useJobPolling` (see `DocumentListRow`). This view only covers what job
 * polling cannot see: a document left `pending` / `processing` by an earlier
 * session, whose job id no endpoint can give back. For those, the whole list is
 * refetched on an interval, which stops as soon as none are left.
 */
const { t } = useAppI18n()
const store = useDocumentsStore()

let timer: ReturnType<typeof setTimeout> | null = null

function clearTimer(): void {
  if (timer !== null) {
    clearTimeout(timer)
    timer = null
  }
}

function schedule(): void {
  if (timer !== null || !store.hasUntrackedActiveDocument) {
    return
  }
  timer = setTimeout(() => {
    timer = null
    void tick()
  }, DOCUMENT_POLL_INTERVAL_MS)
}

async function tick(): Promise<void> {
  if (!store.hasUntrackedActiveDocument) {
    return
  }
  await store.load({ silent: true })
  schedule()
}

watch(
  () => store.hasUntrackedActiveDocument,
  (active) => {
    if (active) {
      schedule()
    } else {
      clearTimer()
    }
  },
)

onMounted(async () => {
  await store.ensureLoaded()
  schedule()
})

onUnmounted(clearTimer)
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h2 class="page-title">{{ t('pages.documents.title') }}</h2>
      <p class="page-description">{{ t('pages.documents.description') }}</p>
    </header>

    <DocumentIntakePanel />

    <p v-if="store.loadError !== null" class="documents__error">
      {{ store.loadError }}
      <AppButton variant="secondary" @click="store.load()">
        {{ t('documents.list.reload') }}
      </AppButton>
    </p>

    <p v-if="store.loading" class="documents__status">{{ t('documents.list.loading') }}</p>

    <template v-else-if="store.documents.length > 0">
      <p class="documents__status">
        {{ t('documents.list.count', { count: store.documents.length }) }}
      </p>
      <ul class="documents__list">
        <DocumentListRow
          v-for="item in store.documents"
          :key="item.id"
          :document="item"
          :job-id="store.parseJobIdOf(item.id)"
        />
      </ul>
    </template>

    <EmptyState
      v-else-if="store.loaded"
      :title="t('documents.list.emptyTitle')"
      :description="t('documents.list.emptyDescription')"
    />
  </section>
</template>

<style scoped>
.documents__list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  list-style: none;
  padding: 0;
}

.documents__status {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.documents__error {
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
