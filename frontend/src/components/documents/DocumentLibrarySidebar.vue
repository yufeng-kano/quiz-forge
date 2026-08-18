<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from 'vue'

import type { Folder } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
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
 * The 文件庫 left column (docs/decisions/2026-08-18-documents-library-single-filelist.md).
 *
 * One list — 全部 / 未分類 / each folder — that is both the view switcher and
 * the folder manager: clicking an item filters the right-hand table (all /
 * unfiled / that folder's documents), and the page persists the selection.
 * 全部 and 未分類 share the folder items' visual: full width, borderless,
 * active by weight and color only, plain counts.
 *
 * The create-folder band at the top of the column is always visible (G2): a
 * full-width click target with a centred plus and a hairline below.
 *
 * The 未分類 item and every folder item are drop targets for a document row
 * (全部 is not), and the `move` event is raised to the page, which owns the
 * single move handler shared with the row menu's 移至資料夾 fallback (drag
 * must not be the only way to move a document).
 *
 * Counts are derived from the document list this column filters, not from the
 * server's `document_count`: the page holds every document anyway, so counting
 * them here means a folder's count and the rows next to it can never disagree
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
  <nav class="library" :aria-label="t('documents.folders.label')">
    <ul class="library__list">
      <li class="library__item">
        <button
          class="library__select"
          :class="{ 'library__select--active': filter === 'all' }"
          type="button"
          :aria-pressed="filter === 'all'"
          @click="filter = 'all'"
        >
          <span class="library__name text-ellipsis">{{ t('documents.folders.all') }}</span>
          <span class="library__count">{{ counts.total }}</span>
        </button>
      </li>

      <li
        class="library__item"
        :class="{ 'library__item--drop': isDropTarget(null) }"
        @dragenter="onDragEnter(null, $event)"
        @dragover="onDragOver(null, $event)"
        @dragleave="onDragLeave(null)"
        @drop="onDrop(null, $event)"
      >
        <button
          class="library__select"
          :class="{ 'library__select--active': filter === 'unfiled' }"
          type="button"
          :aria-pressed="filter === 'unfiled'"
          @click="filter = 'unfiled'"
        >
          <span class="library__name text-ellipsis">{{ t('documents.folders.unfiled') }}</span>
          <span class="library__count">{{ counts.unfiled }}</span>
        </button>
      </li>

      <!-- One hairline separates the virtual views (全部 / 未分類) from the real folders. -->
      <li v-if="folders.folders.length > 0" class="library__divider" aria-hidden="true"></li>

      <!-- The create control sits between the divider and the first folder: the
           icon is centred, but the full-width row is the click target. -->
      <li class="library__create-row">
        <button
          class="library__create-band-button"
          type="button"
          :disabled="creating"
          :aria-label="t('documents.folders.createAriaLabel')"
          :title="t('documents.folders.createAriaLabel')"
          @click="startCreating"
        >
          <AppIcon name="plus" :size="16" />
        </button>
      </li>

      <li v-if="creating" class="library__create-row">
        <form class="library__create" @submit.prevent="submitCreate">
          <input
            ref="newNameInput"
            v-model="newName"
            class="form-input"
            type="text"
            :aria-label="t('documents.folders.nameLabel')"
            :placeholder="t('documents.folders.namePlaceholder')"
            @keyup.esc="cancelCreating"
          />
          <div class="library__form-actions">
            <AppButton type="submit" size="sm" :disabled="newName.trim() === '' || busy">
              {{ t('documents.folders.createSubmit') }}
            </AppButton>
            <AppButton variant="ghost" size="sm" :disabled="busy" @click="cancelCreating">
              {{ t('common.cancel') }}
            </AppButton>
          </div>
        </form>
      </li>

      <li
        v-for="folder in folders.folders"
        :key="folder.id"
        class="library__item"
        :class="{ 'library__item--drop': isDropTarget(folder.id) }"
        @dragenter="onDragEnter(folder.id, $event)"
        @dragover="onDragOver(folder.id, $event)"
        @dragleave="onDragLeave(folder.id)"
        @drop="onDrop(folder.id, $event)"
      >
        <form
          v-if="editingId === folder.id"
          class="library__rename"
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
          <div class="library__form-actions">
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
            class="library__select"
            :class="{ 'library__select--active': filter === folder.id }"
            type="button"
            :aria-pressed="filter === folder.id"
            @click="filter = folder.id"
          >
            <span class="library__name text-ellipsis" :title="folder.name">{{ folder.name }}</span>
            <span class="library__count">{{ countOf(folder) }}</span>
          </button>

          <span class="library__actions">
            <AppButton
              variant="ghost"
              icon
              size="sm"
              :disabled="busy"
              :aria-label="t('documents.folders.rename')"
              :title="t('documents.folders.rename')"
              @click="startEditing(folder)"
            >
              <AppIcon name="edit" :size="16" />
            </AppButton>
            <AppButton
              variant="ghost"
              icon
              size="sm"
              :disabled="busy"
              :aria-label="t('documents.folders.delete')"
              :title="t('documents.folders.delete')"
              @click="removeFolder(folder)"
            >
              <AppIcon name="trash" :size="16" />
            </AppButton>
          </span>
        </template>
      </li>
    </ul>

    <p v-if="folders.loading" class="library__hint">{{ t('documents.folders.loading') }}</p>
    <p v-else-if="folders.loadError !== null" class="library__error">{{ folders.loadError }}</p>
    <p v-else-if="folders.folders.length === 0" class="library__hint">
      {{ t('documents.folders.empty') }}
    </p>
  </nav>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 0;
  height: 100%;
  padding: var(--space-3) 0 0;
}

/* The create-folder control (G2): a row between the divider and the first
   folder — full-width click target with a centred plus, no border of its own,
   and the same row height as the list items (identical padding to
   `.library__select`; the 16px icon is shorter than the text line box). */
.library__create-row {
  flex: none;
}

.library__create-band-button {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  padding: var(--space-1) var(--space-2);
  border: none;
  background: none;
  color: var(--color-text-muted);
  cursor: pointer;
  transition:
    color 0.15s ease,
    background-color 0.15s ease;
}

.library__create-band-button:hover:not(:disabled) {
  color: var(--color-heading);
  background: var(--color-background-mute);
}

.library__create-band-button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}

.library__create-band-button:disabled {
  cursor: default;
}

.library__create,
.library__rename {
  display: flex;
  flex: none;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  min-width: 0;
}

.library__form-actions {
  display: flex;
  gap: var(--space-2);
}

/* The column itself fills the workspace; only this list scrolls. */
.library__list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.1rem;
  min-height: 0;
  overflow-y: auto;
  padding: 0;
  list-style: none;
}

.library__divider {
  flex: none;
  margin: var(--space-2) 0;
  border-top: 1px solid var(--color-border);
}

/* Borderless and full width: the 1px transparent border exists only so the
   drag-over highlight has an edge to fill, and it never shows at rest. */
.library__item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  min-width: 0;
  border: 1px solid transparent;
}

.library__item--drop {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.library__select {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-1) var(--space-2);
  border: none;
  background: none;
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-size-md);
  text-align: left;
  cursor: pointer;
}

.library__select:hover {
  background: var(--color-background-mute);
}

/* Selected state is weight and color only — no border, no background. */
.library__select--active {
  color: var(--color-heading);
  font-weight: 600;
}

.library__name {
  min-width: 0;
}

.library__count {
  flex: none;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

/* Row actions fade out until the folder is hovered or focused, so the column
   reads as a filter list first. Faded rather than `display: none`, which would
   take them out of the tab order and make them unreachable by keyboard — the
   space they occupy is reserved either way, so nothing shifts when they appear. */
.library__actions {
  display: flex;
  flex: none;
  gap: var(--space-1);
  opacity: 0;
  transition: opacity 0.15s ease;
}

.library__item:hover .library__actions,
.library__item:focus-within .library__actions {
  opacity: 1;
}

.library__hint,
.library__error {
  flex: none;
  font-size: var(--font-size-md);
}

.library__hint {
  color: var(--color-text-muted);
}

.library__error {
  color: var(--color-status-failed-text);
  overflow-wrap: anywhere;
}

/* Without a pointer there is no hover to reveal them */
@media (hover: none) {
  .library__actions {
    opacity: 1;
  }
}
</style>