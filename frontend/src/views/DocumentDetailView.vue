<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { retryPage } from '@/api'
import AppButton from '@/components/AppButton.vue'
import DocumentChunkCard from '@/components/DocumentChunkCard.vue'
import DocumentPageCard from '@/components/DocumentPageCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useDocumentDetail } from '@/composables/useDocumentDetail'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'
import { buildCategoryIndex, resolveCategoryPath } from '@/utils/categories'

/** `:id` comes from the router's `props: true`; route params are always strings. */
const props = defineProps<{ id: string }>()

const { t } = useAppI18n()
const store = useDocumentsStore()

const documentId = computed<number | null>(() => {
  const parsed = Number(props.id)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
})

/**
 * The job worth watching: the one a page retry just created, otherwise the
 * `parse_document` job the documents store remembers from this session's
 * upload / import. Without one, the document itself is still refetched on an
 * interval — only the progress line and the job error are unavailable.
 */
const retryJobId = ref<number | null>(null)

const activeJobId = computed<number | null>(() => {
  if (retryJobId.value !== null) {
    return retryJobId.value
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
const pageErrors = ref<Record<number, string>>({})
const retryingJob = ref(false)

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

// A finished job means new pages, chunks or a new document status.
watch(jobIsActive, (active, wasActive) => {
  if (wasActive === true && !active) {
    void refresh()
  }
})

async function onRetryPage(pageId: number): Promise<void> {
  retryingPageId.value = pageId
  delete pageErrors.value[pageId]
  try {
    const job = await retryPage(pageId)
    // Watch the new `parse_page` job: it keeps the document polling alive even
    // while the job is still queued and the page status has not moved yet.
    retryJobId.value = job.id
    await refresh()
  } catch (cause) {
    pageErrors.value[pageId] = translateApiError(cause)
  } finally {
    retryingPageId.value = null
  }
}

async function onRetryJob(): Promise<void> {
  retryingJob.value = true
  try {
    await retryFailedJob()
  } finally {
    retryingJob.value = false
  }
}
</script>

<template>
  <section class="page">
    <RouterLink class="detail__back" :to="{ name: 'documents' }">
      {{ t('documentDetail.back') }}
    </RouterLink>

    <EmptyState
      v-if="documentId === null"
      :title="t('documentDetail.invalidId')"
      :description="t('documentDetail.invalidIdDescription')"
    />

    <template v-else>
      <header class="page-header">
        <h2 class="page-title">{{ detail?.title ?? t('pages.documentDetail.title') }}</h2>
        <p class="page-subtitle">{{ t('pages.documentDetail.subtitle', { id: documentId }) }}</p>
      </header>

      <p v-if="error !== null" class="detail__error">
        {{ error }}
        <AppButton variant="secondary" @click="reload()">
          {{ t('documentDetail.reload') }}
        </AppButton>
      </p>

      <p v-if="loading" class="detail__status">{{ t('documentDetail.loading') }}</p>

      <template v-if="detail !== null">
        <section class="detail__summary-block">
          <div class="detail__facts">
            <StatusBadge :status="detail.status" />
            <span>{{ t(`documents.sourceType.${detail.source_type}`) }}</span>
            <span>{{
              t('documentDetail.createdAt', { datetime: formatDateTime(detail.created_at) })
            }}</span>
          </div>

          <p v-if="detail.source_url !== null" class="detail__source">
            <span class="detail__label">{{ t('documentDetail.sourceUrl') }}</span>
            <a :href="detail.source_url" target="_blank" rel="noopener noreferrer">
              {{ detail.source_url }}
            </a>
          </p>

          <div
            v-if="detail.summary !== null && detail.summary.trim() !== ''"
            class="detail__summary"
          >
            <span class="detail__label">{{ t('documentDetail.summary') }}</span>
            <p>{{ detail.summary }}</p>
          </div>

          <p v-if="jobIsActive" class="detail__progress">
            <span class="detail__label">{{ t('documentDetail.jobProgress') }}</span>
            <ProgressText :progress="progress" />
          </p>

          <p v-if="jobFailureText !== null" class="detail__error">
            {{ jobFailureText }}
            <AppButton variant="secondary" :disabled="retryingJob" @click="onRetryJob">
              {{ t('documentDetail.retryJob') }}
            </AppButton>
          </p>

          <p v-if="jobRequestError !== null" class="detail__error">{{ jobRequestError }}</p>
        </section>

        <section class="detail__section">
          <header class="detail__section-head">
            <h3 class="detail__section-title">{{ t('documentDetail.pages.title') }}</h3>
            <span class="detail__section-count">
              {{ t('documentDetail.pages.count', { count: pages.length }) }}
            </span>
          </header>

          <div v-if="pages.length > 0" class="detail__cards">
            <DocumentPageCard
              v-for="page in pages"
              :key="page.id"
              :page="page"
              :retrying="retryingPageId === page.id"
              :error="pageErrors[page.id] ?? null"
              @retry="onRetryPage"
            />
          </div>
          <EmptyState
            v-else
            :title="t('documentDetail.pages.emptyTitle')"
            :description="t('documentDetail.pages.emptyDescription')"
          />
        </section>

        <section class="detail__section">
          <header class="detail__section-head">
            <h3 class="detail__section-title">{{ t('documentDetail.chunks.title') }}</h3>
            <span class="detail__section-count">
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
      </template>
    </template>
  </section>
</template>

<style scoped>
.detail__back {
  align-self: flex-start;
  font-size: 0.875rem;
}

.detail__status {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.detail__error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-status-failed-border);
  border-radius: 8px;
  background: var(--color-status-failed-bg);
  color: var(--color-status-failed-text);
  overflow-wrap: anywhere;
}

.detail__summary-block {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1rem 1.2rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background-soft);
}

.detail__facts {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 1rem;
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.detail__label {
  margin-right: 0.5rem;
  color: var(--color-heading);
  font-size: 0.875rem;
  font-weight: 600;
}

.detail__source {
  overflow-wrap: anywhere;
}

.detail__summary p {
  margin-top: 0.25rem;
}

.detail__progress {
  display: flex;
  align-items: baseline;
}

.detail__section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.detail__section-head {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.detail__section-title {
  font-size: 1.0625rem;
}

.detail__section-count {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.detail__cards {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
