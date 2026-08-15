<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'

import { DOCUMENT_POLL_INTERVAL_MS, type DocumentListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import DocumentIntakePanel from '@/components/documents/DocumentIntakePanel.vue'
import DocumentRowActions from '@/components/documents/DocumentRowActions.vue'
import DocumentStatusCell from '@/components/documents/DocumentStatusCell.vue'
import DataTable from '@/components/ui/DataTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DataTableColumn } from '@/components/ui/dataTable'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'
import { useToastsStore } from '@/stores/toasts'

/**
 * 文件列表 — the intake card row above the table, then every document with its
 * pipeline state.
 *
 * Rows created in this session carry a job id and refresh themselves through
 * their status cell. This view only covers what job polling cannot see: a
 * document left `pending` / `processing` by an earlier session, whose job id no
 * endpoint can give back. For those, the whole list is refetched on an
 * interval, which stops as soon as none are left.
 */
const { t } = useAppI18n()
const router = useRouter()
const store = useDocumentsStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

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
    <PageHeader
      :title="t('pages.documents.title')"
      :subtitle="t('documents.list.count', { count: store.documents.length })"
    >
      <template #actions>
        <AppButton variant="secondary" :disabled="store.loading" @click="store.load()">
          {{ t('documents.list.reload') }}
        </AppButton>
      </template>
    </PageHeader>

    <DocumentIntakePanel />

    <p v-if="store.loadError !== null" class="error-banner">
      {{ store.loadError }}
      <AppButton variant="secondary" @click="store.load()">
        {{ t('documents.list.reload') }}
      </AppButton>
    </p>

    <DataTable
      :columns="columns"
      :rows="store.documents"
      :row-key="(item: DocumentListItem) => item.id"
      :loading="store.loading"
      :empty-title="t('documents.list.emptyTitle')"
      :empty-description="t('documents.list.emptyDescription')"
      clickable-rows
      @row-click="openDetail"
    >
      <template #title="{ row }">
        <span class="documents__title">{{ row.title }}</span>
        <a
          v-if="row.source_url !== null"
          class="documents__source"
          :href="row.source_url"
          target="_blank"
          rel="noopener noreferrer"
          @click.stop
        >
          {{ row.source_url }}
        </a>
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
  </div>
</template>

<style scoped>
/* The intake row sits above the table, so the table gets less of the viewport
   than the design system's default assumes */
.page {
  --data-table-max-height: max(22rem, calc(100vh - 28rem));
}

.documents__title {
  display: block;
  color: var(--color-heading);
  font-weight: 600;
  overflow-wrap: anywhere;
}

.documents__source {
  display: block;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}
</style>
