<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'

import { DOCUMENT_POLL_INTERVAL_MS, isReadyEntityStatus, type DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import DocumentActiveList from '@/components/documents/DocumentActiveList.vue'
import DocumentIntakePanel from '@/components/documents/DocumentIntakePanel.vue'
import DocumentRowActions from '@/components/documents/DocumentRowActions.vue'
import DocumentStatusCell from '@/components/documents/DocumentStatusCell.vue'
import DocumentTitleCell from '@/components/documents/DocumentTitleCell.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import DataTable from '@/components/ui/DataTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DataTableColumn } from '@/components/ui/dataTable'
import type { AppTabItem } from '@/components/ui/tabs'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'
import { useToastsStore } from '@/stores/toasts'
import { matchesQuery, normalizeQuery } from '@/utils/search'

/**
 * 文件區 — two tabs (docs/frontend.md 頁面清單): 上傳 is the intake workspace
 * (drop zone, URL import and the parses still running), 文件庫 is the whole
 * library as a sortable table.
 *
 * Rows created in this session carry a job id and refresh themselves through
 * their status cell. This view only covers what job polling cannot see: a
 * document left `pending` / `processing` by an earlier session, whose job id no
 * endpoint can give back. For those, the whole list is refetched on an
 * interval, which stops as soon as none are left. That timer belongs to the
 * page rather than to a tab, so a parse started under 上傳 keeps being watched
 * while 文件庫 is on screen.
 *
 * The search box narrows the rows client-side: `GET /api/v1/documents` returns
 * the whole list in one response, so filtering it here is instant and a server
 * round trip would only add latency.
 */
const { t } = useAppI18n()
const route = useRoute()
const router = useRouter()
const store = useDocumentsStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

const TAB_IDS = ['library', 'upload'] as const

type DocumentsTab = (typeof TAB_IDS)[number]

/** 文件庫 is what `/documents` opens on; `?tab=upload` deep-links the other one. */
const DEFAULT_TAB: DocumentsTab = 'library'
const TAB_QUERY_KEY = 'tab'

function isDocumentsTab(value: unknown): value is DocumentsTab {
  return TAB_IDS.some((tab) => tab === value)
}

/**
 * The active tab lives in the route query, so a reload or a back navigation
 * returns to the tab the user was on. The default tab carries no query
 * parameter: `/documents` and `/documents?tab=library` must not be two
 * different-looking URLs for the same view.
 */
const activeTab = computed<DocumentsTab>({
  get: () => {
    const raw = route.query[TAB_QUERY_KEY]
    const value = Array.isArray(raw) ? raw[0] : raw
    return isDocumentsTab(value) ? value : DEFAULT_TAB
  },
  set: (tab) => {
    if (tab === activeTab.value) {
      return
    }
    const query: LocationQueryRaw = { ...route.query }
    if (tab === DEFAULT_TAB) {
      delete query[TAB_QUERY_KEY]
    } else {
      query[TAB_QUERY_KEY] = tab
    }
    // `replace`: switching tabs is not a step the back button should retrace
    // once per click, it only has to survive a reload.
    void router.replace({ query })
  },
})

const search = ref('')

const query = computed(() => normalizeQuery(search.value))

const visibleDocuments = computed<DocumentListItem[]>(() =>
  store.documents.filter((document) => matchesQuery(document.title, query.value)),
)

const isFiltering = computed(() => query.value !== '')

/** Everything the pipeline has not finished: parsing, queued, or failed. */
const inProgressDocuments = computed<DocumentListItem[]>(() =>
  store.documents.filter((document) => !isReadyEntityStatus(document.status)),
)

const tabs = computed<AppTabItem<DocumentsTab>[]>(() => [
  { id: 'library', label: t('documents.tabs.library') },
  {
    id: 'upload',
    label: t('documents.tabs.upload'),
    badge:
      inProgressDocuments.value.length === 0 ? undefined : String(inProgressDocuments.value.length),
  },
])

const subtitle = computed(() => {
  if (activeTab.value === 'upload') {
    return t('documents.intake.subtitle')
  }
  return isFiltering.value
    ? t('documents.list.filteredCount', {
        total: store.documents.length,
        count: visibleDocuments.value.length,
      })
    : t('documents.list.count', { count: store.documents.length })
})

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
    width: '8rem',
    nowrap: true,
  },
  {
    key: 'status',
    label: t('documents.columns.status'),
    sortValue: (item) => item.status,
    width: '14rem',
  },
  {
    key: 'page_count',
    label: t('documents.columns.pageCount'),
    value: (item) => t('documents.row.pageCount', { count: item.page_count }),
    sortValue: (item) => item.page_count,
    align: 'end',
    width: '6rem',
    nowrap: true,
  },
  {
    key: 'created_at',
    label: t('documents.columns.createdAt'),
    value: (item) => formatDateTime(item.created_at),
    sortValue: (item) => item.created_at,
    width: '10rem',
    nowrap: true,
  },
  {
    key: 'actions',
    label: t('documents.columns.actions'),
    labelHidden: true,
    align: 'end',
    width: '13rem',
    nowrap: true,
  },
])

function openDetail(item: DocumentListItem): void {
  void router.push({ name: 'document-detail', params: { id: String(item.id) } })
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

/** A new document's job only shows up under 上傳, so that is where the user goes. */
function onDocumentCreated(): void {
  activeTab.value = 'upload'
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
  <div class="page">
    <PageHeader :title="t('pages.documents.title')" :subtitle="subtitle">
      <template #actions>
        <AppButton variant="secondary" :disabled="store.loading" @click="store.load()">
          {{ t('documents.list.reload') }}
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="store.loadError !== null" class="error-banner">
      {{ store.loadError }}
      <AppButton variant="secondary" @click="store.load()">
        {{ t('documents.list.reload') }}
      </AppButton>
    </p>

    <AppTabs v-model="activeTab" :tabs="tabs" :label="t('documents.tabs.label')">
      <template #upload>
        <DocumentIntakePanel @created="onDocumentCreated" />
        <DocumentActiveList
          :documents="inProgressDocuments"
          :loading="store.loading"
          @delete="onDelete"
        />
      </template>

      <template #library>
        <div class="documents__toolbar">
          <input
            v-model="search"
            class="form-input documents__search"
            type="search"
            :aria-label="t('documents.list.search')"
            :placeholder="t('documents.list.searchPlaceholder')"
          />
        </div>

        <DataTable
          :columns="columns"
          :rows="visibleDocuments"
          :row-key="(item: DocumentListItem) => item.id"
          :loading="store.loading"
          :empty-title="
            isFiltering ? t('documents.list.noMatchTitle') : t('documents.list.emptyTitle')
          "
          :empty-description="
            isFiltering
              ? t('documents.list.noMatchDescription')
              : t('documents.list.emptyDescription')
          "
          clickable-rows
          @row-click="openDetail"
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
                @delete="onDelete"
              />
            </div>
          </template>
        </DataTable>
      </template>
    </AppTabs>
  </div>
</template>

<style scoped>
/* The tab bar and the search row sit above the table, so it gets less of the
   viewport than the design system's default assumes */
.page {
  --data-table-max-height: max(22rem, calc(100vh - 24rem));
}

.documents__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.documents__search {
  width: min(18rem, 60vw);
}
</style>
