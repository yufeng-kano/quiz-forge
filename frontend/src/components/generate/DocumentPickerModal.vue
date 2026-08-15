<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { isReadyEntityStatus, type DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAppI18n } from '@/i18n'
import { useDocumentsStore } from '@/stores/documents'
import { matchesQuery, normalizeQuery } from '@/utils/search'

/**
 * Document half of the 出題 scope, as a modal picker.
 *
 * The whole document list is offered rather than only the eligible part: a
 * document that is still parsing or has failed is shown with its status and
 * cannot be ticked, which answers 「為什麼我的文件不在清單裡」 instead of leaving
 * it unexplained. Only `ready` is selectable because only a fully parsed
 * document has chunks to generate from
 * (`backend.questions.selection.find_eligible_chunks`).
 *
 * The list scrolls inside its own box under a fixed search field, so the modal
 * never grows with the number of documents (docs/frontend.md 清單有界原則).
 */
const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{ close: [] }>()

const selectedIds = defineModel<number[]>('selectedIds', { required: true })

const { t } = useAppI18n()
const store = useDocumentsStore()

const search = ref('')

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      return
    }
    // Every opening starts fresh: the previous keyword is rarely the next one.
    search.value = ''
    await store.ensureLoaded()
  },
)

const query = computed(() => normalizeQuery(search.value))

const filtered = computed<DocumentListItem[]>(() =>
  store.documents.filter((document) => matchesQuery(document.title, query.value)),
)

function isSelectable(document: DocumentListItem): boolean {
  return isReadyEntityStatus(document.status)
}

function isSelected(documentId: number): boolean {
  return selectedIds.value.includes(documentId)
}

function toggle(documentId: number): void {
  selectedIds.value = isSelected(documentId)
    ? selectedIds.value.filter((id) => id !== documentId)
    : [...selectedIds.value, documentId]
}

function clearAll(): void {
  selectedIds.value = []
}
</script>

<template>
  <AppModal
    :open="props.open"
    size="lg"
    :title="t('generate.scope.documents.modalTitle')"
    @close="emit('close')"
  >
    <div class="picker">
      <label class="form-field">
        <span class="form-label">{{ t('generate.scope.documents.search') }}</span>
        <input
          v-model="search"
          class="form-input"
          type="search"
          :placeholder="t('generate.scope.documents.searchPlaceholder')"
        />
      </label>

      <p v-if="store.loading && store.documents.length === 0" class="form-hint">
        {{ t('generate.scope.documents.loading') }}
      </p>
      <p v-else-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>
      <p v-else-if="store.documents.length === 0" class="form-hint">
        {{ t('generate.scope.documents.empty') }}
      </p>
      <p v-else-if="filtered.length === 0" class="form-hint">
        {{ t('generate.scope.documents.noMatch') }}
      </p>

      <ul v-else class="picker__list">
        <li v-for="document in filtered" :key="document.id">
          <label class="picker__row" :class="{ 'picker__row--disabled': !isSelectable(document) }">
            <input
              type="checkbox"
              :checked="isSelected(document.id)"
              :disabled="!isSelectable(document)"
              :aria-label="t('generate.scope.documents.checkbox', { title: document.title })"
              @change="toggle(document.id)"
            />

            <span class="picker__main">
              <span class="picker__title text-ellipsis" :title="document.title">
                {{ document.title }}
              </span>
              <span class="picker__meta">
                <span>{{ t(`documents.sourceType.${document.source_type}`) }}</span>
                <span>{{ t('documents.row.pageCount', { count: document.page_count }) }}</span>
              </span>
            </span>

            <StatusBadge :status="document.status" />
          </label>
        </li>
      </ul>

      <p class="form-hint">{{ t('generate.scope.documents.readyOnly') }}</p>
    </div>

    <template #actions>
      <AppButton variant="ghost" :disabled="selectedIds.length === 0" @click="clearAll">
        {{ t('generate.scope.clear') }}
      </AppButton>
      <AppButton @click="emit('close')">{{ t('generate.scope.done') }}</AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* The bounded box of the picker: the search field above it stays put and only
   the rows scroll, however many documents there are */
.picker__list {
  display: flex;
  flex-direction: column;
  max-height: min(24rem, 50vh);
  overflow-y: auto;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  list-style: none;
}

.picker__row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-hairline);
  cursor: pointer;
}

.picker__list > li:last-child .picker__row {
  border-bottom: none;
}

.picker__row:hover {
  background: var(--color-background-soft);
}

.picker__row--disabled {
  color: var(--color-text-faint);
  cursor: not-allowed;
}

.picker__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.picker__title {
  color: var(--color-heading);
  font-weight: 600;
}

.picker__row--disabled .picker__title {
  color: var(--color-text-muted);
  font-weight: normal;
}

.picker__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-3);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}
</style>
