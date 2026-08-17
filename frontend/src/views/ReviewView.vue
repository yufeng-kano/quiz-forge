<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import type { QuestionListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ReviewFilters from '@/components/questions/ReviewFilters.vue'
import ReviewQuestionCard from '@/components/questions/ReviewQuestionCard.vue'
import AppPagination from '@/components/ui/AppPagination.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { useQuestionsStore } from '@/stores/questions'
import { useToastsStore } from '@/stores/toasts'

/**
 * 審題 — every `draft` question, newest first (docs/question-bank.md 審題流程).
 *
 * The list is refetched on every visit, silently when something is already on
 * screen, because questions arrive from generation jobs running in the
 * background. Individual cards leave the list as they are adopted or discarded;
 * the count in the header always reflects what the server still has waiting.
 *
 * Batch adopt/discard runs the calls one after another rather than in
 * parallel: each is a small write, the backend is a single worker process, and
 * a sequential run is what makes a partial failure reportable — a question that
 * fails gets its own toast and the batch carries on, so one 409 never abandons
 * the other forty.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

/** Placeholder cards while the first page loads. */
const SKELETON_CARDS = 3

const selectedIds = ref<number[]>([])
const batchProgress = ref<{ done: number; total: number } | null>(null)

const visibleIds = computed(() => store.drafts.map((question) => question.id))
const selectedSet = computed(() => new Set(selectedIds.value))
const selectedCount = computed(() => selectedIds.value.length)
const isBatchRunning = computed(() => batchProgress.value !== null)

const allVisibleSelected = computed(
  () => visibleIds.value.length > 0 && visibleIds.value.every((id) => selectedSet.value.has(id)),
)

function isSelected(question: QuestionListItem): boolean {
  return selectedSet.value.has(question.id)
}

function toggleSelect(question: QuestionListItem): void {
  selectedIds.value = isSelected(question)
    ? selectedIds.value.filter((id) => id !== question.id)
    : [...selectedIds.value, question.id]
}

function toggleSelectAll(): void {
  selectedIds.value = allVisibleSelected.value ? [] : [...visibleIds.value]
}

/** Drop ids that are no longer on screen (adopted, discarded, filtered away). */
watch(visibleIds, (ids) => {
  const present = new Set(ids)
  const kept = selectedIds.value.filter((id) => present.has(id))
  if (kept.length !== selectedIds.value.length) {
    selectedIds.value = kept
  }
})

async function runBatch(action: 'approve' | 'reject'): Promise<void> {
  const ids = [...selectedIds.value]
  if (ids.length === 0 || isBatchRunning.value) {
    return
  }
  const confirmed = await confirm({
    title: action === 'approve' ? t('review.batch.approveTitle') : t('review.batch.rejectTitle'),
    message:
      action === 'approve'
        ? t('review.batch.approveMessage', { count: ids.length })
        : t('review.batch.rejectMessage', { count: ids.length }),
    confirmLabel:
      action === 'approve' ? t('review.batch.approveConfirm') : t('review.batch.rejectConfirm'),
    tone: action === 'approve' ? 'default' : 'danger',
  })
  if (!confirmed) {
    return
  }

  batchProgress.value = { done: 0, total: ids.length }
  let succeeded = 0
  let failed = 0
  for (const id of ids) {
    try {
      if (action === 'approve') {
        await store.approve(id)
      } else {
        await store.reject(id)
      }
      succeeded += 1
    } catch (error) {
      failed += 1
      toasts.error(t('review.batch.itemFailed', { id, error: translateApiError(error) }))
    }
    batchProgress.value = { done: succeeded + failed, total: ids.length }
  }
  batchProgress.value = null
  selectedIds.value = []

  if (failed === 0) {
    toasts.success(
      action === 'approve'
        ? t('review.batch.approveDone', { count: succeeded })
        : t('review.batch.rejectDone', { count: succeeded }),
    )
  } else {
    toasts.error(t('review.batch.partial', { succeeded, failed }))
  }
  // The page has holes now (rows left the queue); refill it from the server.
  await store.loadDrafts({ silent: true })
}

onMounted(async () => {
  await store.loadDrafts({ silent: store.draftsLoaded })
})

// A filter or page change is a new query, so it always goes back to the server.
watch([() => store.draftFilters, () => store.draftsPage], () => {
  void store.loadDrafts({ silent: true })
})
</script>

<template>
  <div class="page">
    <PageHeader :title="t('review.pageTitle', { count: formatCount(store.draftsTotal) })">
      <template v-if="selectedCount > 0" #meta>
        <span>{{ t('review.batch.selected', { count: selectedCount }) }}</span>
      </template>

      <template #actions>
        <AppButton
          variant="secondary"
          :disabled="store.draftsLoading || isBatchRunning"
          @click="store.loadDrafts()"
        >
          {{ t('review.reload') }}
        </AppButton>
      </template>
    </PageHeader>

    <ReviewFilters />

    <p v-if="store.draftsError !== null" class="error-banner">
      {{ store.draftsError }}
      <AppButton variant="secondary" @click="store.loadDrafts()">
        {{ t('review.reload') }}
      </AppButton>
    </p>

    <div v-if="store.draftCount > 0" class="card review__batch">
      <label class="review__select-all">
        <input
          type="checkbox"
          :checked="allVisibleSelected"
          :disabled="isBatchRunning"
          @change="toggleSelectAll"
        />
        <span>{{ t('review.batch.selectAll', { count: store.draftCount }) }}</span>
      </label>

      <AppButton
        size="sm"
        :disabled="selectedCount === 0 || isBatchRunning"
        @click="runBatch('approve')"
      >
        {{ t('review.batch.approve', { count: selectedCount }) }}
      </AppButton>
      <AppButton
        variant="secondary"
        size="sm"
        :disabled="selectedCount === 0 || isBatchRunning"
        @click="runBatch('reject')"
      >
        {{ t('review.batch.reject', { count: selectedCount }) }}
      </AppButton>

      <span v-if="batchProgress !== null" class="muted-text">
        {{ t('review.batch.progress', { done: batchProgress.done, total: batchProgress.total }) }}
      </span>
    </div>

    <ul v-if="store.draftsLoading && store.draftCount === 0" class="review__list">
      <li v-for="index in SKELETON_CARDS" :key="`skeleton-${index}`" class="card">
        <AppSkeleton width="30%" />
        <AppSkeleton />
        <AppSkeleton width="70%" />
      </li>
    </ul>

    <template v-else-if="store.draftCount > 0">
      <ul class="review__list">
        <li v-for="question in store.drafts" :key="question.id">
          <ReviewQuestionCard
            :question="question"
            :selected="isSelected(question)"
            :busy="isBatchRunning"
            @toggle-select="toggleSelect(question)"
          />
        </li>
      </ul>

      <AppPagination
        v-if="store.draftsPageCount > 1"
        :page="store.draftsPage"
        :page-count="store.draftsPageCount"
        :total="store.draftsTotal"
        :disabled="store.draftsLoading || isBatchRunning"
        @change="store.setDraftsPage($event)"
      />
    </template>

    <EmptyState
      v-else-if="store.draftsLoaded"
      :title="t('review.emptyTitle')"
      :description="
        store.hasActiveDraftFilter ? t('review.emptyFiltered') : t('review.emptyDescription')
      "
    >
      <template #actions>
        <RouterLink class="review__link" :to="{ name: 'generate' }">
          {{ t('review.goGenerate') }}
        </RouterLink>
      </template>
    </EmptyState>
  </div>
</template>

<style scoped>
.review__batch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.review__select-all {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-right: auto;
  cursor: pointer;
}

.review__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: 0;
  list-style: none;
}

.review__link {
  color: var(--color-accent);
}
</style>
