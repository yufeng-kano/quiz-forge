<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { DOCUMENT_POLL_INTERVAL_MS, isReadyEntityStatus, type DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import DocumentIntakePanel from '@/components/documents/DocumentIntakePanel.vue'
import DocumentLibrarySidebar from '@/components/documents/DocumentLibrarySidebar.vue'
import DocumentMoveModal from '@/components/documents/DocumentMoveModal.vue'
import DocumentRenameModal from '@/components/documents/DocumentRenameModal.vue'
import DocumentRowActions from '@/components/documents/DocumentRowActions.vue'
import DocumentStatusCell from '@/components/documents/DocumentStatusCell.vue'
import DocumentTitleCell from '@/components/documents/DocumentTitleCell.vue'
import {
  matchesFolderFilter,
  setDocumentDragPayload,
  type FolderFilter,
  type FolderTarget,
} from '@/components/documents/folders'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import DataTable from '@/components/ui/DataTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DataTableColumn } from '@/components/ui/dataTable'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { useDocumentsStore } from '@/stores/documents'
import { useFoldersStore } from '@/stores/folders'
import { useToastsStore } from '@/stores/toasts'
import { matchesQuery, normalizeQuery } from '@/utils/search'
import { readStoredValue, writeStoredValue } from '@/utils/storage'

/**
 * Documents workspace (docs/frontend.md, L1–L4): left column (filelist:
 * 全部 / 未分類 / each folder) + fill-height table under a compact header.
 * Upload lives in a header modal; `?tab=upload` still opens it, then
 * `replace`s the query away so `/documents` and `/documents?tab=library`
 * never look like two different pages.
 *
 * Rows created in this session carry a job id and refresh themselves through
 * their status cell. This view only covers what job polling cannot see: a
 * document left `pending` / `processing` by an earlier session, whose job id no
 * endpoint can give back. For those, the whole list is refetched on an
 * interval, which stops as soon as none are left.
 *
 * The search box and the left column narrow the rows client-side:
 * `GET /api/v1/documents` returns the whole list in one response, so filtering
 * it here is instant and a server round trip (`?folder_id=`, `?unfiled=true`)
 * would only add latency — and it keeps the folder counts derived from exactly
 * the rows being filtered, so a move updates both at once.
 */
const { t } = useAppI18n()
const route = useRoute()
const router = useRouter()
const store = useDocumentsStore()
const folders = useFoldersStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

const TAB_QUERY_KEY = 'tab'

function tabQuery(): string | null {
  const raw = route.query[TAB_QUERY_KEY]
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value : null
}

const intakeOpen = ref(false)

function stripTabQuery(): void {
  if (tabQuery() === null) {
    return
  }
  const query = { ...route.query }
  delete query[TAB_QUERY_KEY]
  void router.replace({ query })
}

function openIntake(): void {
  intakeOpen.value = true
}

function closeIntake(): void {
  intakeOpen.value = false
  stripTabQuery()
}

watch(
  () => tabQuery(),
  (tab) => {
    if (tab === 'upload') {
      intakeOpen.value = true
      return
    }
    if (tab !== null) {
      stripTabQuery()
    }
  },
  { immediate: true },
)

const search = ref('')

/* --------------------------------------------- left column state (G1) */

const LEFT_FILELIST_STORAGE_KEY = 'quiz-forge:documents-left-filelist:v1'

function readStoredFilelistFilter(): FolderFilter {
  const value = readStoredValue(LEFT_FILELIST_STORAGE_KEY)
  if (value === 'all' || value === 'unfiled') {
    return value
  }
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : 'all'
}

/**
 * Which item of the left column's filelist is selected, persisted so a revisit
 * lands on the last view. A stored value in a shape no build wrote (anything
 * that is not 'all' / 'unfiled' / a positive integer) falls back to the
 * default rather than crashing.
 */
const filter = ref<FolderFilter>(readStoredFilelistFilter())

watch(filter, (value) => writeStoredValue(LEFT_FILELIST_STORAGE_KEY, value))

/**
 * A persisted folder id whose folder was deleted in the meantime falls back to
 * 全部. Until the folder list has loaded there is nothing to check it against,
 * so the stored value is trusted in the meantime.
 */
watch(
  () => folders.loaded,
  (loaded) => {
    if (!loaded || typeof filter.value !== 'number') {
      return
    }
    if (!folders.folders.some((folder) => folder.id === filter.value)) {
      filter.value = 'all'
    }
  },
  { immediate: true },
)

const query = computed(() => normalizeQuery(search.value))

const visibleDocuments = computed<DocumentListItem[]>(() =>
  store.documents.filter(
    (document) =>
      matchesFolderFilter(document, filter.value) &&
      matchesQuery(document.title, query.value),
  ),
)

const isFiltering = computed(() => query.value !== '' || filter.value !== 'all')

/** Everything the pipeline has not finished: parsing, queued, or failed. */
const inProgressDocuments = computed<DocumentListItem[]>(() =>
  store.documents.filter((document) => !isReadyEntityStatus(document.status)),
)

/** Header count: how many documents the table is showing, of how many there are. */
const headerCount = computed(() =>
  isFiltering.value
    ? t('documents.headerCountFiltered', {
        total: formatCount(store.documents.length),
        count: formatCount(visibleDocuments.value.length),
      })
    : t('documents.headerCount', { count: formatCount(store.documents.length) }),
)

const columns = computed<DataTableColumn<DocumentListItem>[]>(() => [
  {
    key: 'title',
    label: t('documents.columns.title'),
    sortValue: (item) => item.title,
  },
  {
    key: 'source_type',
    label: t('documents.columns.sourceType'),
    value: (item) => t(`documents.sourceType.${item.source_type}`),
    sortValue: (item) => item.source_type,
    width: '7rem',
    nowrap: true,
  },
  {
    key: 'status',
    label: t('documents.columns.status'),
    sortValue: (item) => item.status,
    // Wide enough for the parse progress line (「3 / 12 頁（25%）」) to stay
    // readable under the status word instead of being cut by the cell.
    width: '9rem',
  },
  {
    key: 'page_count',
    label: t('documents.columns.pageCount'),
    value: (item) => t('documents.row.pageCount', { count: item.page_count }),
    sortValue: (item) => item.page_count,
    align: 'end',
    width: '4.5rem',
    nowrap: true,
  },
  {
    key: 'created_at',
    label: t('documents.columns.createdAt'),
    value: (item) => formatDateTime(item.created_at),
    sortValue: (item) => item.created_at,
    width: '9.5rem',
    nowrap: true,
  },
  {
    key: 'actions',
    label: t('documents.columns.actions'),
    labelHidden: true,
    align: 'end',
    width: '2.75rem',
  },
])

function openDetail(item: DocumentListItem): void {
  void router.push({ name: 'document-detail', params: { id: String(item.id) } })
}

/* -------------------------------------------------------- move to folder */

/** Puts the row's id into the drag, which the folder column reads on drop. */
function onRowDragStart(item: DocumentListItem, event: DragEvent): void {
  if (event.dataTransfer !== null) {
    setDocumentDragPayload(event.dataTransfer, item.id)
  }
}

/**
 * The one move handler, shared by a drop on the folder column and by the row
 * menu's 移至資料夾 dialog. A dropped id that no longer matches a row (a stale
 * drag, a foreign payload that happened to parse) is ignored, and a move to
 * where the document already is is not sent at all.
 */
async function moveDocument(documentId: number, target: FolderTarget): Promise<void> {
  const item = store.documents.find((document) => document.id === documentId)
  if (item === undefined || item.folder_id === target) {
    return
  }
  const title = item.title
  try {
    await store.move(documentId, target)
    if (target === null) {
      toasts.success(t('documents.folders.movedToUnfiled', { title }))
      return
    }
    const name = folders.nameOf(target)
    toasts.success(
      name === null
        ? t('documents.folders.movedToUnknown', { title })
        : t('documents.folders.moved', { title, folder: name }),
    )
  } catch (error) {
    // A folder deleted in the meantime comes back as 404 — say so rather than
    // leaving the row looking moved.
    toasts.error(translateApiError(error))
  }
}

const movingDocument = ref<DocumentListItem | null>(null)

function openMove(item: DocumentListItem): void {
  movingDocument.value = item
}

async function onMoveSelected(target: FolderTarget): Promise<void> {
  const item = movingDocument.value
  movingDocument.value = null
  if (item !== null) {
    await moveDocument(item.id, target)
  }
}

/* ---------------------------------------------------------------- rename */

const renamingDocument = ref<DocumentListItem | null>(null)
const renaming = ref(false)

function openRename(item: DocumentListItem): void {
  renamingDocument.value = item
}

async function onRenameSubmit(title: string): Promise<void> {
  const item = renamingDocument.value
  if (item === null) {
    return
  }
  renaming.value = true
  try {
    const updated = await store.rename(item.id, title)
    toasts.success(t('documents.rename.renamed', { title: updated.title }))
    renamingDocument.value = null
  } catch (error) {
    // Kept open on failure so the rejected title can be corrected in place.
    toasts.error(translateApiError(error))
  } finally {
    renaming.value = false
  }
}

async function onDelete(item: DocumentListItem): Promise<void> {
  const confirmed = await confirm({
    title: t('documents.row.deleteTitle'),
    message: t('documents.row.deleteConfirmQuestion', { title: item.title }),
    confirmLabel: t('documents.row.deleteConfirm'),
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }
  try {
    await store.remove(item.id)
    toasts.success(t('documents.row.deleted', { title: item.title }))
  } catch (error) {
    toasts.error(translateApiError(error))
  }
}

/** A finished upload belongs in the library; the new row appears there. */
function onDocumentCreated(): void {
  closeIntake()
}

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
  <div class="page page--workspace">
    <PageHeader :page-name="t('nav.documents')">
      <template #meta>{{ headerCount }}</template>

      <template #actions>
        <AppButton
          variant="secondary"
          icon
          :disabled="store.loading"
          :aria-label="t('documents.list.reload')"
          :title="t('documents.list.reload')"
          @click="store.load()"
        >
          <AppIcon name="refresh" :size="16" />
        </AppButton>
        <AppButton @click="openIntake">{{ t('documents.intake.open') }}</AppButton>
      </template>
    </PageHeader>

    <p v-if="store.loadError !== null" class="error-banner">
      {{ store.loadError }}
      <AppButton
        variant="secondary"
        icon
        :aria-label="t('documents.list.reload')"
        :title="t('documents.list.reload')"
        @click="store.load()"
      >
        <AppIcon name="refresh" :size="16" />
      </AppButton>
    </p>

    <div class="workspace">
      <DocumentLibrarySidebar v-model="filter" class="workspace__sidebar" @move="moveDocument" />

      <div class="workspace__main">
        <div class="workspace__toolbar">
          <input
            v-model="search"
            class="workspace__search"
            type="search"
            :aria-label="t('documents.list.search')"
            :placeholder="t('documents.list.searchPlaceholder')"
          />
        </div>

        <p v-if="inProgressDocuments.length > 0" class="workspace__summary">
          {{
            t('documents.list.activeSummary', { count: formatCount(inProgressDocuments.length) })
          }}
        </p>

        <DataTable
          :columns="columns"
          :rows="visibleDocuments"
          :row-key="(item: DocumentListItem) => item.id"
          :loading="store.loading"
          :empty-title="
            isFiltering ? t('documents.list.noMatchTitle') : t('documents.list.emptyTitle')
          "
          fill-height
          clickable-rows
          draggable-rows
          @row-click="openDetail"
          @row-drag-start="onRowDragStart"
        >
          <template #title="{ row }">
            <DocumentTitleCell :document="row" />
          </template>

          <template #status="{ row }">
            <DocumentStatusCell :document="row" :job-id="store.parseJobIdOf(row.id)" />
          </template>

          <template #actions="{ row }">
            <div @click.stop>
              <DocumentRowActions
                :document="row"
                :job-id="store.parseJobIdOf(row.id)"
                @rename="openRename"
                @move="openMove"
                @delete="onDelete"
              />
            </div>
          </template>
        </DataTable>
      </div>
    </div>

    <AppModal
      :open="intakeOpen"
      :title="t('documents.intake.modalTitle')"
      size="lg"
      @close="closeIntake"
    >
      <DocumentIntakePanel @created="onDocumentCreated" />
    </AppModal>

    <DocumentRenameModal
      :open="renamingDocument !== null"
      :title="renamingDocument?.title ?? ''"
      :busy="renaming"
      @close="renamingDocument = null"
      @submit="onRenameSubmit"
    />

    <DocumentMoveModal
      :open="movingDocument !== null"
      :document="movingDocument"
      @close="movingDocument = null"
      @select="onMoveSelected"
    />
  </div>
</template>

<style scoped>
.page > .error-banner {
  margin: var(--space-3) 0 0;
}

.workspace {
  display: grid;
  flex: 1;
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: 0;
  min-height: 0;
  /* Same bleed as PageHeader: cancel the .page gutter so the column and table
     line up with the header rule (L8). */
  margin: 0 calc(-1 * var(--content-padding-x));
}

.workspace__sidebar {
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--color-border);
}

.workspace__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0;
  min-width: 0;
  min-height: 0;
}

/* Search is the table's first band (L7): no boxed .form-input chrome, a rule
   under the field closes the band, then the table header follows. */
.workspace__toolbar {
  flex: none;
  border-bottom: 1px solid var(--color-border);
}

.workspace__search {
  display: block;
  width: 100%;
  margin: 0;
  padding: var(--space-3) var(--space-4);
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  appearance: none;
}

.workspace__search:focus {
  outline: none;
}

.workspace__search:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}

/* Says how many documents are still parsing — real information, so it gets a
   readable size and the running tone rather than shrunken grey (D20). */
.workspace__summary {
  flex: none;
  padding: var(--space-2) var(--space-4);
  color: var(--color-status-running-text);
  font-size: var(--font-size-md);
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
  }

  .workspace__sidebar {
    height: min(16rem, 30vh);
    border-right: none;
    border-bottom: 1px solid var(--color-border);
  }
}
</style>
