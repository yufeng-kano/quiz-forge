<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BankQuestionCard from '@/components/questions/BankQuestionCard.vue'
import ExportSelectionBar from '@/components/questions/ExportSelectionBar.vue'
import QuestionFilters from '@/components/questions/QuestionFilters.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAppI18n } from '@/i18n'
import { useQuestionsStore } from '@/stores/questions'

/**
 * 題庫 — browsing of `approved` questions, rendered with the same components as
 * the review page, with the answers visible.
 *
 * Filters live in the store and are watched here: any change refetches the list
 * silently, so the previous result stays on screen until the new one arrives.
 * Selecting questions for the Word export writes to the export-selection store,
 * which is what `/exports` reads later.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()

const visibleIds = computed(() => store.bank.map((question) => question.id))

onMounted(async () => {
  await store.loadBank({ silent: store.bankLoaded })
})

watch(
  () => store.filters,
  () => {
    void store.loadBank({ silent: true })
  },
  { deep: true },
)
</script>

<template>
  <div class="page">
    <PageHeader :title="t('pages.questions.title')" :subtitle="t('pages.questions.description')" />

    <QuestionFilters />

    <ExportSelectionBar :visible-ids="visibleIds" />

    <p v-if="store.bankError !== null" class="bank__error">
      {{ store.bankError }}
      <AppButton variant="secondary" @click="store.loadBank()">{{ t('bank.reload') }}</AppButton>
    </p>

    <p v-if="store.bankLoading" class="bank__status">{{ t('bank.loading') }}</p>

    <template v-else-if="store.bankCount > 0">
      <p class="bank__status">{{ t('bank.count', { count: store.bankCount }) }}</p>
      <ul class="bank__list">
        <li v-for="question in store.bank" :key="question.id">
          <BankQuestionCard :question="question" />
        </li>
      </ul>
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
  </div>
</template>

<style scoped>
.bank__list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 0;
  list-style: none;
}

.bank__status {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.bank__error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-status-failed-border);
  border-radius: 8px;
  background: var(--color-status-failed-bg);
  color: var(--color-status-failed-text);
}

.bank__link {
  color: var(--color-accent);
}
</style>
