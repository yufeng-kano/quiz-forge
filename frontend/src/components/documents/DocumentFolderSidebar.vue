<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from 'vue'

import type { Folder } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'
import { useFoldersStore } from '@/stores/folders'
import { useToastsStore } from '@/stores/toasts'
import {
  hasDocumentDragPayload,
  readDocumentDragPayload,
  type FolderFilter,
  type FolderTarget,
} from './folders'

/**
 * 資料夾欄 of the 文件庫 tab (docs/frontend.md 基礎架構).
 *
 * Two jobs in one column, because they are the same list:
 * - it filters the library — 全部 / 未分類 / one folder — through `v-model`;
 * - every entry except 全部 is a drop target for a document row, and the
 *   `move` event is raised to the page, which owns the single move handler
 *   shared with the row menu's 移至資料夾 fallback (drag must not be the only
 *   way to move a document).
 *
 * Counts are derived from the document list this column filters, not from the
 * server's `document_count`: the page holds every document anyway, so counting
 * them here means a folder's badge and the rows next to it can never disagree
 * after a move, with no refetch.
 *
 * Creating, renaming and deleting folders is done inline here (this is the
 * only place folders exist in the UI). Deleting is confirmed first because it
 * unfiles whatever was inside; since the server does that itself, the document
 * list is refetched afterwards so the rows do not keep a dead `folder_id`.
 */
const filter = defineModel<FolderFilter>({ required: true })

const emit = defineEmits<{ move: [documentId: number, target: FolderTarget] }>()

const { t } = useAppI18n()
const folders = useFoldersStore()
const documents = useDocumentsStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

void folders.ensureLoaded()

const counts = computed(() => {
  const perFolder = new Map<number, number>()
  let unfiled = 0
  for (const document of documents.documents) {
    if (document.folder_id === null) {
      unfiled += 1
      continue
    }
    perFolder.set(document.folder_id, (perFolder.get(document.folder_id) ?? 0) + 1)
  }
  return { perFolder, unfiled, total: documents.documents.length }
})

function countOf(folder: Folder): number {
  return counts.value.perFolder.get(folder.id) ?? 0
}

/* ------------------------------------------------------------------ drop */

/**
 * Which entry is currently under the pointer, as a stable key.
 *
 * `dragenter` / `dragleave` also fire when the pointer crosses a child element
 * of the row, so the entered/left pairs are counted instead of trusting a
 * single `dragleave` — otherwise the highlight would flicker off whenever the
 * pointer moved over the folder name.
 */
const dropTargetKey = ref<string | null>(null)
let dropDepth = 0

function targetKey(target: FolderTarget): string {
  return target === null ? 'unfiled' : `folder-${target}`
}

function isDropTarget(target: FolderTarget): boolean {
  return dropTargetKey.value === targetKey(target)
}

function clearDropTarget(): void {
  dropTargetKey.value = null
  dropDepth = 0
}

function onDragEnter(target: FolderTarget, event: DragEvent): void {
  if (!hasDocumentDragPayload(event.dataTransfer)) {
    return
  }
  const key = targetKey(target)
  if (dropTargetKey.value !== key) {
    dropTargetKey.value = key
    dropDepth = 0
  }
  dropDepth += 1
}

function onDragLeave(target: FolderTarget): void {
  if (dropTargetKey.value !== targetKey(target)) {
    return
  }
  dropDepth -= 1
  if (dropDepth <= 0) {
    clearDropTarget()
  }
}

/** Only a document-row drag is accepted; anything else keeps the browser default. */
function onDragOver(target: FolderTarget, event: DragEvent): void {
  const dataTransfer = event.dataTransfer
  if (!hasDocumentDragPayload(dataTransfer)) {
    return
  }
  // Preventing the default is literally what marks this element as a valid
  // drop target; without it the `drop` event never fires.
  event.preventDefault()
  if (dataTransfer !== null) {
    dataTransfer.dropEffect = 'move'
  }
  if (dropTargetKey.value !== targetKey(target)) {
    dropTargetKey.value = targetKey(target)
    dropDepth = 1
  }
}

function onDrop(target: FolderTarget, event: DragEvent): void {
  // The browser's own handling of a drop (opening a dropped file or link) is
  // never what this column wants, whatever was dropped.
  event.preventDefault()
  clearDropTarget()
  const documentId = readDocumentDragPayload(event.dataTransfer)
  if (documentId === null) {
    // Something else was dropped here (a file, a link, a text selection):
    // ignore it rather than acting on a guess.
    return
  }
  emit('move', documentId, target)
}

/* ---------------------------------------------------------------- create */

const creating = ref(false)
const newName = ref('')
const busy = ref(false)
const newNameInput = useTemplateRef<HTMLInputElement>('newNameInput')

async function startCreating(): Promise<void> {
  creating.value = true
  newName.value = ''
  await nextTick()
  newNameInput.value?.focus()
}

function cancelCreating(): void {
  creating.value = false
  newName.value = ''
}

async function submitCreate(): Promise<void> {
  const name = newName.value.trim()
  if (name === '' || busy.value) {
    return
  }
  busy.value = true
  try {
    const created = await folders.create(name)
    toasts.success(t('documents.folders.created', { name: created.name }))
    cancelCreating()
  } catch (error) {
    // A duplicate name is a 409 whose detail names the conflict; show it.
    toasts.error(translateApiError(error))
  } finally {
    busy.value = false
  }
}

/* ------------------------------------------------------- rename / delete */

const editingId = ref<number | null>(null)
const editingName = ref('')
/** Inside `v-for`, Vue collects template refs into an array — at most one
    folder is ever being edited, so the single entry is what gets focused. */
const editingInput = useTemplateRef<HTMLInputElement | HTMLInputElement[]>('editingInput')

async function startEditing(folder: Folder): Promise<void> {
  cancelCreating()
  editingId.value = folder.id
  editingName.value = folder.name
  await nextTick()
  const input = editingInput.value
  const element = Array.isArray(input) ? input[0] : input
  element?.focus()
}

function cancelEditing(): void {
  editingId.value = null
  editingName.value = ''
}

async function submitRename(folder: Folder): Promise<void> {
  const name = editingName.value.trim()
  if (name === '' || busy.value) {
    return
  }
  if (name === folder.name) {
    cancelEditing()
    return
  }
  busy.value = true
  try {
    const updated = await folders.rename(folder.id, name)
    toasts.success(t('documents.folders.renamed', { name: updated.name }))
    cancelEditing()
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    busy.value = false
  }
}

async function removeFolder(folder: Folder): Promise<void> {
  const confirmed = await confirm({
    title: t('documents.folders.deleteTitle'),
    message: t('documents.folders.deleteMessage', { name: folder.name }),
    confirmLabel: t('documents.folders.deleteConfirm'),
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }
  busy.value = true
  try {
    await folders.remove(folder.id)
    toasts.success(t('documents.folders.deleted', { name: folder.name }))
    if (filter.value === folder.id) {
      filter.value = 'all'
    }
    // The server unfiled every document that was inside; the rows in memory
    // still point at the folder that is now gone.
    await documents.load({ silent: true })
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <nav class="folders" :aria-label="t('documents.folders.label')">
    <div class="folders__head">
      <h2 class="folders__title">{{ t('documents.folders.title') }}</h2>
      <AppButton variant="ghost" size="sm" :disabled="creating" @click="startCreating">
        {{ t('documents.folders.create') }}
      </AppButton>
    </div>

    <form v-if="creating" class="folders__create" @submit.prevent="submitCreate">
      <input
        ref="newNameInput"
        v-model="newName"
        class="form-input"
        type="text"
        :aria-label="t('documents.folders.nameLabel')"
        :placeholder="t('documents.folders.namePlaceholder')"
        @keyup.esc="cancelCreating"
      />
      <div class="folders__create-actions">
        <AppButton type="submit" size="sm" :disabled="newName.trim() === '' || busy">
          {{ t('documents.folders.createSubmit') }}
        </AppButton>
        <AppButton variant="ghost" size="sm" :disabled="busy" @click="cancelCreating">
          {{ t('common.cancel') }}
        </AppButton>
      </div>
    </form>

    <ul class="folders__list">
      <li class="folders__item">
        <button
          class="folders__select"
          :class="{ 'folders__select--active': filter === 'all' }"
          type="button"
          :aria-pressed="filter === 'all'"
          @click="filter = 'all'"
        >
          <span class="folders__name text-ellipsis">{{ t('documents.folders.all') }}</span>
          <span class="folders__count">{{ counts.total }}</span>
        </button>
      </li>

      <li
        class="folders__item"
        :class="{ 'folders__item--drop': isDropTarget(null) }"
        @dragenter="onDragEnter(null, $event)"
        @dragover="onDragOver(null, $event)"
        @dragleave="onDragLeave(null)"
        @drop="onDrop(null, $event)"
      >
        <button
          class="folders__select"
          :class="{ 'folders__select--active': filter === 'unfiled' }"
          type="button"
          :aria-pressed="filter === 'unfiled'"
          @click="filter = 'unfiled'"
        >
          <span class="folders__name text-ellipsis">{{ t('documents.folders.unfiled') }}</span>
          <span class="folders__count">{{ counts.unfiled }}</span>
        </button>
      </li>

      <li
        v-for="folder in folders.folders"
        :key="folder.id"
        class="folders__item"
        :class="{ 'folders__item--drop': isDropTarget(folder.id) }"
        @dragenter="onDragEnter(folder.id, $event)"
        @dragover="onDragOver(folder.id, $event)"
        @dragleave="onDragLeave(folder.id)"
        @drop="onDrop(folder.id, $event)"
      >
        <form
          v-if="editingId === folder.id"
          class="folders__rename"
          @submit.prevent="submitRename(folder)"
        >
          <input
            ref="editingInput"
            v-model="editingName"
            class="form-input"
            type="text"
            :aria-label="t('documents.folders.renameLabel', { name: folder.name })"
            @keyup.esc="cancelEditing"
          />
          <div class="folders__create-actions">
            <AppButton type="submit" size="sm" :disabled="editingName.trim() === '' || busy">
              {{ t('documents.folders.renameSubmit') }}
            </AppButton>
            <AppButton variant="ghost" size="sm" :disabled="busy" @click="cancelEditing">
              {{ t('common.cancel') }}
            </AppButton>
          </div>
        </form>

        <template v-else>
          <button
            class="folders__select"
            :class="{ 'folders__select--active': filter === folder.id }"
            type="button"
            :aria-pressed="filter === folder.id"
            @click="filter = folder.id"
          >
            <span class="folders__name text-ellipsis" :title="folder.name">{{ folder.name }}</span>
            <span class="folders__count">{{ countOf(folder) }}</span>
          </button>

          <span class="folders__actions">
            <AppButton variant="ghost" size="sm" :disabled="busy" @click="startEditing(folder)">
              {{ t('documents.folders.rename') }}
            </AppButton>
            <AppButton variant="ghost" size="sm" :disabled="busy" @click="removeFolder(folder)">
              {{ t('documents.folders.delete') }}
            </AppButton>
          </span>
        </template>
      </li>
    </ul>

    <p v-if="folders.loading" class="form-hint">{{ t('documents.folders.loading') }}</p>
    <p v-else-if="folders.loadError !== null" class="form-error">{{ folders.loadError }}</p>
    <p v-else-if="folders.folders.length === 0" class="form-hint">
      {{ t('documents.folders.empty') }}
    </p>
    <p v-else class="form-hint">{{ t('documents.folders.dragHint') }}</p>
  </nav>
</template>

<style scoped>
.folders {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
}

.folders__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.folders__title {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.folders__create,
.folders__rename {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  min-width: 0;
}

.folders__create-actions {
  display: flex;
  gap: var(--space-2);
}

/* Bounded height with its own scroll: the column must not grow the page as
   folders pile up (docs/frontend.md 清單有界原則) */
.folders__list {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  max-height: min(28rem, 50vh);
  overflow-y: auto;
  padding: 0;
  list-style: none;
}

.folders__item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  min-width: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

/* Drag-over highlight: the design system's low-chroma accent, so the target
   folder is unmistakable without introducing a new colour */
.folders__item--drop {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.folders__select {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-1) var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-size-md);
  text-align: left;
  cursor: pointer;
}

.folders__select:hover {
  background: var(--color-background-mute);
}

.folders__select--active {
  background: var(--color-accent-soft);
  color: var(--color-heading);
  font-weight: 600;
}

.folders__name {
  min-width: 0;
}

.folders__count {
  flex: none;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

/* Row actions fade out until the folder is hovered or focused, so the column
   reads as a filter list first. Faded rather than `display: none`, which would
   take them out of the tab order and make them unreachable by keyboard — the
   space they occupy is reserved either way, so nothing shifts when they appear. */
.folders__actions {
  display: flex;
  flex: none;
  gap: var(--space-1);
  opacity: 0;
  transition: opacity 0.15s ease;
}

.folders__item:hover .folders__actions,
.folders__item:focus-within .folders__actions {
  opacity: 1;
}

/* Without a pointer there is no hover to reveal them */
@media (hover: none) {
  .folders__actions {
    opacity: 1;
  }
}
</style>
