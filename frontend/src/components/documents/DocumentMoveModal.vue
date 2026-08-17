<script setup lang="ts">
import { watch } from 'vue'

import type { DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAppI18n } from '@/i18n'
import { useFoldersStore } from '@/stores/folders'
import type { FolderTarget } from './folders'

/**
 * 移至資料夾 — the keyboard-reachable way to do what dragging a row onto the
 * folder column does, so drag and drop is never the only route (a pointer is
 * not a requirement for moving a document).
 *
 * Picking a destination is the whole interaction, so a click on a row is the
 * confirmation: it emits the target and the caller performs the `PATCH` and
 * closes the dialog. The folder the document already sits in is shown as such
 * and cannot be picked — a move to where it already is would be a pointless
 * request.
 */
const props = defineProps<{
  open: boolean
  /** The document being moved; `null` while the dialog is closed. */
  document: DocumentListItem | null
}>()

const emit = defineEmits<{ close: []; select: [target: FolderTarget] }>()

const { t } = useAppI18n()
const folders = useFoldersStore()

watch(
  () => props.open,
  async (open) => {
    if (open) {
      await folders.ensureLoaded()
    }
  },
)

function isCurrent(target: FolderTarget): boolean {
  return props.document !== null && props.document.folder_id === target
}

function select(target: FolderTarget): void {
  if (isCurrent(target)) {
    return
  }
  emit('select', target)
}
</script>

<template>
  <AppModal :open="props.open" :title="t('documents.folders.moveTitle')" @close="emit('close')">
    <!-- Which document is being moved is the only thing the dialog title does
         not already say, so it is shown as the plain title, not a sentence. -->
    <p
      v-if="props.document !== null"
      class="move__subject text-ellipsis"
      :title="props.document.title"
    >
      {{ props.document.title }}
    </p>

    <p v-if="folders.loading && folders.folders.length === 0" class="form-hint">
      {{ t('documents.folders.loading') }}
    </p>
    <p v-else-if="folders.loadError !== null" class="form-error">{{ folders.loadError }}</p>

    <ul class="move__list">
      <li>
        <button class="move__row" type="button" :disabled="isCurrent(null)" @click="select(null)">
          <span class="move__name text-ellipsis">{{ t('documents.folders.unfiled') }}</span>
          <span v-if="isCurrent(null)" class="move__current">
            {{ t('documents.folders.moveCurrent') }}
          </span>
        </button>
      </li>
      <li v-for="folder in folders.folders" :key="folder.id">
        <button
          class="move__row"
          type="button"
          :disabled="isCurrent(folder.id)"
          @click="select(folder.id)"
        >
          <span class="move__name text-ellipsis" :title="folder.name">{{ folder.name }}</span>
          <span v-if="isCurrent(folder.id)" class="move__current">
            {{ t('documents.folders.moveCurrent') }}
          </span>
        </button>
      </li>
    </ul>

    <p v-if="folders.folders.length === 0 && !folders.loading" class="form-hint">
      {{ t('documents.folders.moveEmpty') }}
    </p>

    <template #actions>
      <AppButton variant="secondary" @click="emit('close')">{{ t('common.cancel') }}</AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
/* Bounded box with its own scroll, however many folders exist
   (docs/frontend.md 清單有界原則) */
.move__list {
  display: flex;
  flex-direction: column;
  max-height: min(20rem, 45vh);
  overflow-y: auto;
  margin-top: var(--space-3);
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  list-style: none;
}

.move__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  border-bottom: 1px solid var(--color-hairline);
  background: none;
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-size-md);
  text-align: left;
  cursor: pointer;
}

.move__list > li:last-child .move__row {
  border-bottom: none;
}

.move__row:hover:not(:disabled) {
  background: var(--color-background-soft);
}

.move__row:disabled {
  color: var(--color-text-muted);
  cursor: default;
}

.move__subject {
  color: var(--color-heading);
  font-weight: 600;
}

.move__name {
  min-width: 0;
}

.move__current {
  flex: none;
  color: var(--color-text-muted);
}
</style>
