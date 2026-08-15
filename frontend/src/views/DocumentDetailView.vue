<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { rechunkDocument, retryPage } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import DocumentChunkCard from '@/components/documents/DocumentChunkCard.vue'
import DocumentPageCard from '@/components/documents/DocumentPageCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useDocumentDetail } from '@/composables/useDocumentDetail'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'
import { useToastsStore } from '@/stores/toasts'
import { buildCategoryIndex, resolveCategoryPath } from '@/utils/categories'

/** `:id` comes from the router's `props: true`; route params are always strings. */
const props = defineProps<{ id: string }>()

const { t } = useAppI18n()
const router = useRouter()
const store = useDocumentsStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

const documentId = computed<number | null>(() => {
  const parsed = Number(props.id)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
})

/**
 * The job worth watching: the one a page retry or a rechunk just created,
 * otherwise the `parse_document` job the documents store remembers from this
 * session's upload / import. Without one, the document itself is still
 * refetched on an interval — only the progress line and the job error are
 * unavailable.
 */
const trackedJobId = ref<number | null>(null)

const activeJobId = computed<number | null>(() => {
  if (trackedJobId.value !== null) {
    return trackedJobId.value
  }
  const id = documentId.value
  return id === null ? null : store.parseJobIdOf(id)
})

const {
  status: jobStatus,
  progress,
  error: jobError,
  requestError: jobRequestError,
  isActive: jobIsActive,
  retry: retryFailedJob,
} = useJobPolling(activeJobId)

const { detail, loading, error, reload, refresh } = useDocumentDetail(documentId, {
  keepPolling: () => jobIsActive.value,
})

const retryingPageId = ref<number | null>(null)
const retryingJob = ref(false)
const rechunking = ref(false)
const deleting = ref(false)

const jobFailed = computed(() => jobStatus.value === 'failed')

const jobFailureText = computed(() => {
  if (!jobFailed.value) {
    return null
  }
  const reason = jobError.value
  return reason === null || reason.trim() === ''
    ? t('documentDetail.jobFailedNoDetail')
    : t('documentDetail.jobFailed', { error: reason })
})

const pages = computed(() => detail.value?.pages ?? [])
const chunks = computed(() => detail.value?.chunks ?? [])

/** Only a document with parsed pages can be chunked again (the endpoint 409s otherwise). */
const canRechunk = computed(() => pages.value.some((page) => page.status === 'ready'))

/**
 * Category paths for the chunk list. Only the categories embedded in this
 * response can be resolved (see `@/utils/categories`), so the index is rebuilt
 * whenever the chunks change.
 */
const categoryIndex = computed(() => buildCategoryIndex(chunks.value))

function categoryPathOf(chunkIndex: number): string[] {
  const chunk = chunks.value[chunkIndex]
  return chunk === undefined ? [] : resolveCategoryPath(chunk.category, categoryIndex.value)
}

const CHUNKS_ANCHOR_ID = 'document-chunks'

function pageAnchorId(pageId: number): string {
  return `document-page-${pageId}`
}

/** Outline navigation: scroll the content column instead of changing the URL. */
function scrollToAnchor(anchorId: string): void {
  document.getElementById(anchorId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// A finished job means new pages, chunks or a new document status.
watch(jobIsActive, (active, wasActive) => {
  if (wasActive === true && !active) {
    void refresh()
  }
})

async function onRetryPage(pageId: number): Promise<void> {
  retryingPageId.value = pageId
  try {
    const job = await retryPage(pageId)
    // Watch the new `parse_page` job: it keeps the document polling alive even
    // while the job is still queued and the page status has not moved yet.
    trackedJobId.value = job.id
    toasts.success(t('documentDetail.pages.retryQueued'))
    await refresh()
  } catch (cause) {
    toasts.error(translateApiError(cause))
  } finally {
    retryingPageId.value = null
  }
}

async function onRetryJob(): Promise<void> {
  retryingJob.value = true
  try {
    await retryFailedJob()
    const failure = jobRequestError.value
    if (failure === null) {
      toasts.success(t('documentDetail.retryQueued'))
    } else {
      toasts.error(failure)
    }
  } finally {
    retryingJob.value = false
  }
}

async function onRechunk(): Promise<void> {
  const id = documentId.value
  if (id === null) {
    return
  }
  const confirmed = await confirm({
    title: t('documentDetail.rechunk.title'),
    message: t('documentDetail.rechunk.message'),
    confirmLabel: t('documentDetail.rechunk.confirm'),
  })
  if (!confirmed) {
    return
  }
  rechunking.value = true
  try {
    const result = await rechunkDocument(id)
    trackedJobId.value = result.job_id
    toasts.success(t('documentDetail.rechunk.queued'))
    await refresh()
  } catch (cause) {
    toasts.error(translateApiError(cause))
  } finally {
    rechunking.value = false
  }
}

async function onDelete(): Promise<void> {
  const id = documentId.value
  if (id === null) {
    return
  }
  const title = detail.value?.title ?? String(id)
  const confirmed = await confirm({
    title: t('documents.row.deleteTitle'),
    message: t('documents.row.deleteConfirmQuestion', { title }),
    confirmLabel: t('documents.row.deleteConfirm'),
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }
  deleting.value = true
  try {
    await store.remove(id)
    toasts.success(t('documents.row.deleted', { title }))
    await router.push({ name: 'documents' })
  } catch (cause) {
    toasts.error(translateApiError(cause))
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="page">
    <EmptyState
      v-if="documentId === null"
      :title="t('documentDetail.invalidId')"
      :description="t('documentDetail.invalidIdDescription')"
    />

    <template v-else>
      <PageHeader
        :title="detail?.title ?? t('pages.documentDetail.title')"
        :subtitle="t('pages.documentDetail.subtitle', { id: documentId })"
      >
        <template #meta>
          <StatusBadge v-if="detail !== null" :status="detail.status" />
          <span v-if="detail !== null">{{ t(`documents.sourceType.${detail.source_type}`) }}</span>
          <span v-if="detail !== null">
            {{ t('documentDetail.createdAt', { datetime: formatDateTime(detail.created_at) }) }}
          </span>
          <ProgressText v-if="jobIsActive" :progress="progress" />
        </template>

        <template #actions>
          <AppButton
            v-if="jobFailed"
            variant="secondary"
            :disabled="retryingJob"
            @click="onRetryJob"
          >
            {{ retryingJob ? t('documentDetail.retrying') : t('documentDetail.retryJob') }}
          </AppButton>
          <AppButton
            v-if="canRechunk"
            variant="secondary"
            :disabled="rechunking || jobIsActive"
            @click="onRechunk"
          >
            {{
              rechunking ? t('documentDetail.rechunk.queueing') : t('documentDetail.rechunk.action')
            }}
          </AppButton>
          <AppButton variant="ghost" :disabled="deleting" @click="onDelete">
            {{ t('documents.row.delete') }}
          </AppButton>
        </template>
      </PageHeader>

      <p v-if="error !== null" class="error-banner">
        {{ error }}
        <AppButton variant="secondary" @click="reload()">
          {{ t('documentDetail.reload') }}
        </AppButton>
      </p>

      <p v-if="jobFailureText !== null" class="error-banner">{{ jobFailureText }}</p>
      <p v-if="jobRequestError !== null" class="error-banner">{{ jobRequestError }}</p>

      <p v-if="loading" class="muted-text">{{ t('documentDetail.loading') }}</p>

      <div v-if="detail !== null" class="detail">
        <nav class="detail__outline" :aria-label="t('documentDetail.outline.label')">
          <p class="detail__outline-title">{{ t('documentDetail.outline.pages') }}</p>

          <ul v-if="pages.length > 0" class="detail__outline-list">
            <li v-for="page in pages" :key="page.id">
              <button
                class="detail__outline-item"
                type="button"
                @click="scrollToAnchor(pageAnchorId(page.id))"
              >
                <span>{{ t('documentDetail.pages.pageNo', { no: page.page_no }) }}</span>
                <StatusBadge :status="page.status" />
              </button>
            </li>
          </ul>
          <p v-else class="detail__outline-empty">{{ t('documentDetail.outline.noPages') }}</p>

          <button
            class="detail__outline-item detail__outline-item--section"
            type="button"
            @click="scrollToAnchor(CHUNKS_ANCHOR_ID)"
          >
            <span>{{ t('documentDetail.chunks.title') }}</span>
            <span class="detail__outline-count">{{ chunks.length }}</span>
          </button>
        </nav>

        <div class="detail__content">
          <section
            v-if="detail.source_url !== null || detail.summary !== null"
            class="card detail__facts"
          >
            <p v-if="detail.source_url !== null" class="detail__fact">
              <span class="detail__fact-label">{{ t('documentDetail.sourceUrl') }}</span>
              <a
                class="detail__fact-url text-ellipsis"
                :href="detail.source_url"
                :title="detail.source_url"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ detail.source_url }}
              </a>
            </p>
            <p v-if="detail.summary !== null && detail.summary.trim() !== ''" class="detail__fact">
              <span class="detail__fact-label">{{ t('documentDetail.summary') }}</span>
              <span>{{ detail.summary }}</span>
            </p>
          </section>

          <section class="detail__section">
            <header class="detail__section-head">
              <h2 class="card-title">{{ t('documentDetail.pages.title') }}</h2>
              <span class="muted-text">
                {{ t('documentDetail.pages.count', { count: pages.length }) }}
              </span>
            </header>

            <div v-if="pages.length > 0" class="detail__cards">
              <div
                v-for="page in pages"
                :id="pageAnchorId(page.id)"
                :key="page.id"
                class="detail__anchor"
              >
                <DocumentPageCard
                  :page="page"
                  :retrying="retryingPageId === page.id"
                  @retry="onRetryPage"
                />
              </div>
            </div>
            <EmptyState
              v-else
              :title="t('documentDetail.pages.emptyTitle')"
              :description="t('documentDetail.pages.emptyDescription')"
            />
          </section>

          <section :id="CHUNKS_ANCHOR_ID" class="detail__section detail__anchor">
            <header class="detail__section-head">
              <h2 class="card-title">{{ t('documentDetail.chunks.title') }}</h2>
              <span class="muted-text">
                {{ t('documentDetail.chunks.count', { count: chunks.length }) }}
              </span>
            </header>

            <div v-if="chunks.length > 0" class="detail__cards">
              <DocumentChunkCard
                v-for="(chunk, chunkIndex) in chunks"
                :key="chunk.id"
                :chunk="chunk"
                :index="chunkIndex + 1"
                :category-path="categoryPathOf(chunkIndex)"
              />
            </div>
            <EmptyState
              v-else
              :title="t('documentDetail.chunks.emptyTitle')"
              :description="t('documentDetail.chunks.emptyDescription')"
            />
          </section>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail {
  display: grid;
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
}

.detail__outline {
  position: sticky;
  /* Clears the page header bar, which sticks at the top of the content region */
  top: calc(var(--page-header-height) + var(--space-4));
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: calc(100vh - var(--page-header-height) - var(--space-6));
  overflow: auto;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
}

.detail__outline-title {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.detail__outline-list {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  list-style: none;
  padding: 0;
}

.detail__outline-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
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

.detail__outline-item:hover {
  background: var(--color-background-mute);
}

.detail__outline-item--section {
  margin-top: var(--space-2);
  border-top: 1px solid var(--color-hairline);
  padding-top: var(--space-2);
  border-radius: 0;
  color: var(--color-heading);
  font-weight: 600;
}

.detail__outline-count {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

.detail__outline-empty {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.detail__content {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
}

.detail__facts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.detail__fact {
  display: flex;
  align-items: baseline;
  min-width: 0;
  overflow-wrap: anywhere;
}

/* A source URL is arbitrarily long and carries no line breaks: one line with
   the whole address in its tooltip (docs/frontend.md 清單有界原則) */
.detail__fact-url {
  min-width: 0;
}

.detail__fact-label {
  flex: none;
  margin-right: var(--space-2);
  color: var(--color-heading);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.detail__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail__section-head {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.detail__cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* Outline clicks scroll here, so the sticky header must not cover the target */
.detail__anchor {
  scroll-margin-top: calc(var(--page-header-height) + var(--space-4));
}

@media (max-width: 900px) {
  .detail {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail__outline {
    position: static;
    max-height: none;
  }
}
</style>
