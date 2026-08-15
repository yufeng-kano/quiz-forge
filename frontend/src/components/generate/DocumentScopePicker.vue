<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { isReadyEntityStatus } from '@/api'
import { useAppI18n } from '@/i18n'
import { useDocumentsStore } from '@/stores/documents'

/**
 * Document half of the 出題 scope.
 *
 * Only `ready` documents are offered: a document still being parsed has no
 * chunks yet, so generating from it could only fail
 * (`backend.questions.selection.find_eligible_chunks`).
 */
const selectedIds = defineModel<number[]>({ required: true })

const { t } = useAppI18n()
const store = useDocumentsStore()

onMounted(async () => {
  await store.ensureLoaded()
})

const readyDocuments = computed(() =>
  store.documents.filter((document) => isReadyEntityStatus(document.status)),
)

function isSelected(documentId: number): boolean {
  return selectedIds.value.includes(documentId)
}

function toggle(documentId: number): void {
  selectedIds.value = isSelected(documentId)
    ? selectedIds.value.filter((id) => id !== documentId)
    : [...selectedIds.value, documentId]
}
</script>

<template>
  <div class="form-field">
    <span class="form-label">{{ t('generate.form.documents') }}</span>

    <p v-if="store.loading" class="form-hint">{{ t('generate.form.documentsLoading') }}</p>
    <p v-else-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>
    <p v-else-if="readyDocuments.length === 0" class="form-hint">
      {{ t('generate.form.documentsEmpty') }}
    </p>

    <ul v-else class="scope-list">
      <li v-for="document in readyDocuments" :key="document.id">
        <label class="scope-list__item">
          <input type="checkbox" :checked="isSelected(document.id)" @change="toggle(document.id)" />
          <span class="scope-list__name">{{ document.title }}</span>
          <span class="scope-list__meta">
            {{ t('documents.row.pageCount', { count: document.page_count }) }}
          </span>
        </label>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.scope-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 16rem;
  overflow-y: auto;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-background);
  list-style: none;
}

.scope-list__item {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  cursor: pointer;
}

.scope-list__name {
  flex: 1;
  overflow-wrap: anywhere;
}

.scope-list__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}
</style>
