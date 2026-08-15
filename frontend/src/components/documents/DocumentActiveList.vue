<script setup lang="ts">
import type { DocumentListItem } from '@/api'
import EmptyState from '@/components/EmptyState.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import { useAppI18n } from '@/i18n'
import { useDocumentsStore } from '@/stores/documents'
import DocumentRowActions from './DocumentRowActions.vue'
import DocumentStatusCell from './DocumentStatusCell.vue'
import DocumentTitleCell from './DocumentTitleCell.vue'

/**
 * The ingestion work still in flight, next to the upload controls that created
 * it: everything that has not reached `ready` — the documents being parsed, and
 * the failed ones, which is where their retry button lives.
 *
 * The rows reuse the same status cell and actions as the 文件庫 table, so job
 * progress, retry and delete behave identically in both tabs; the job
 * subscriptions are per row and shared by job id in `stores/jobs.ts`, so
 * showing a document here as well as in the table costs no extra request.
 */
const props = defineProps<{
  documents: readonly DocumentListItem[]
  /** First list load only; a background refresh keeps the rows on screen. */
  loading: boolean
}>()

const emit = defineEmits<{ delete: [document: DocumentListItem] }>()

const { t } = useAppI18n()
const store = useDocumentsStore()

const SKELETON_ROWS = [0, 1]
</script>

<template>
  <section class="card active-list">
    <header class="active-list__header">
      <h2 class="card-title">{{ t('documents.intake.activeTitle') }}</h2>
      <span class="active-list__count">
        {{ t('documents.intake.activeCount', { count: props.documents.length }) }}
      </span>
    </header>

    <div v-if="props.loading && props.documents.length === 0" class="active-list__skeletons">
      <AppSkeleton v-for="index in SKELETON_ROWS" :key="index" />
    </div>

    <EmptyState
      v-else-if="props.documents.length === 0"
      :title="t('documents.intake.activeEmptyTitle')"
      :description="t('documents.intake.activeEmptyDescription')"
    />

    <ul v-else class="active-list__items">
      <li v-for="document in props.documents" :key="document.id" class="active-list__row">
        <DocumentTitleCell class="active-list__title" :document="document" />
        <DocumentStatusCell :document="document" :job-id="store.parseJobIdOf(document.id)" />
        <DocumentRowActions
          class="active-list__actions"
          :document="document"
          :job-id="store.parseJobIdOf(document.id)"
          @delete="emit('delete', $event)"
        />
      </li>
    </ul>
  </section>
</template>

<style scoped>
.active-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.active-list__header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2) var(--space-3);
}

.active-list__count {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.active-list__skeletons {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* A backlog of failed imports must not turn this tab into an endless page
   (docs/frontend.md 清單有界原則): the list scrolls inside its own box */
.active-list__items {
  display: flex;
  flex-direction: column;
  max-height: min(24rem, 45vh);
  overflow-y: auto;
  padding: 0;
  list-style: none;
}

.active-list__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.active-list__row:last-child {
  border-bottom: none;
}

.active-list__title {
  flex: 1 1 16rem;
}

.active-list__actions {
  margin-left: auto;
}
</style>
