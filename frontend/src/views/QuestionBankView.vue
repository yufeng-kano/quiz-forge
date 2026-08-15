<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BankQuestionCard from '@/components/questions/BankQuestionCard.vue'
import CategoryManagerModal from '@/components/questions/CategoryManagerModal.vue'
import ExportSelectionBar from '@/components/questions/ExportSelectionBar.vue'
import QuestionCreateModal from '@/components/questions/QuestionCreateModal.vue'
import QuestionFilters from '@/components/questions/QuestionFilters.vue'
import AppPagination from '@/components/ui/AppPagination.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import { useQuestionsStore } from '@/stores/questions'

/**
 * 題庫 — browsing of `approved` questions, rendered with the same components as
 * the review page, with the answers visible.
 *
 * Filters and the current page live in the store and are watched here: any
 * change refetches silently, so the previous result stays on screen until the
 * new one arrives. The list is a real page of the server's
 * `{ items, total, limit, offset }` envelope — `total` is the whole result, not
 * what is on screen.
 *
 * Selecting questions for the Word export writes to the export-selection store,
 * which is what `/exports` reads later. Writing a question by hand (新增題目)
 * and copying one (複製) both go through the modals/cards and end in a refresh
 * of whichever list the row landed in — a copy is a draft, so it lands on 審題
 * rather than here.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()

/** Placeholder cards while the first page loads. */
const SKELETON_CARDS = 3

const createOpen = ref(false)
const categoriesOpen = ref(false)

const visibleIds = computed(() => store.bank.map((question) => question.id))

onMounted(async () => {
  await store.loadBank({ silent: store.bankLoaded })
})

watch([() => store.filters, () => store.bankPage], () => {
  void store.loadBank({ silent: true })
})

/** A new question only belongs here when it was saved as approved. */
function onCreated(): void {
  void store.loadBank({ silent: true })
}

/** The copy is a draft, so this page is unchanged; only the queue count moves. */
function onDuplicated(): void {
  void store.loadDrafts({ silent: true })
}

/** A renamed or deleted category can change what the current filter matches. */
function onCategoriesChanged(): void {
  void store.loadBank({ silent: true })
}
</script>

<template>
  <div class="page">
    <PageHeader :title="t('pages.questions.title')" :subtitle="t('pages.questions.description')">
      <template #meta>
        <span>{{ t('bank.total', { count: formatCount(store.bankTotal) }) }}</span>
      </template>

      <template #actions>
        <AppButton variant="secondary" @click="categoriesOpen = true">
          {{ t('bank.categories.action') }}
        </AppButton>
        <AppButton @click="createOpen = true">{{ t('bank.create.action') }}</AppButton>
      </template>
    </PageHeader>

    <QuestionFilters />

    <ExportSelectionBar :visible-ids="visibleIds" />

    <p v-if="store.bankError !== null" class="error-banner">
      {{ store.bankError }}
      <AppButton variant="secondary" @click="store.loadBank()">{{ t('bank.reload') }}</AppButton>
    </p>

    <ul v-if="store.bankLoading && store.bankCount === 0" class="bank__list">
      <li v-for="index in SKELETON_CARDS" :key="`skeleton-${index}`" class="card">
        <AppSkeleton width="30%" />
        <AppSkeleton />
        <AppSkeleton width="70%" />
      </li>
    </ul>

    <template v-else-if="store.bankCount > 0">
      <ul class="bank__list">
        <li v-for="question in store.bank" :key="question.id">
          <BankQuestionCard :question="question" @duplicated="onDuplicated" />
        </li>
      </ul>

      <AppPagination
        v-if="store.bankPageCount > 1"
        :page="store.bankPage"
        :page-count="store.bankPageCount"
        :total="store.bankTotal"
        :disabled="store.bankLoading"
        @change="store.setBankPage($event)"
      />
    </template>

    <EmptyState
      v-else-if="store.bankLoaded"
      :title="t('bank.emptyTitle')"
      :description="t('bank.emptyDescription')"
    >
      <template #actions>
        <RouterLink class="bank__link" :to="{ name: 'review' }">
          {{ t('bank.goReview') }}
        </RouterLink>
      </template>
    </EmptyState>

    <QuestionCreateModal :open="createOpen" @close="createOpen = false" @created="onCreated" />
    <CategoryManagerModal
      :open="categoriesOpen"
      @close="categoriesOpen = false"
      @changed="onCategoriesChanged"
    />
  </div>
</template>

<style scoped>
.bank__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: 0;
  list-style: none;
}

.bank__link {
  color: var(--color-accent);
}
</style>
