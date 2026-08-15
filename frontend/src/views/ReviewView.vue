<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ReviewQuestionCard from '@/components/questions/ReviewQuestionCard.vue'
import { useAppI18n } from '@/i18n'
import { useQuestionsStore } from '@/stores/questions'

/**
 * 審題 — every `draft` question, newest first (docs/question-bank.md 審題流程).
 *
 * The list is refetched on every visit, silently when something is already on
 * screen, because questions arrive from generation jobs running in the
 * background. Individual cards leave the list as they are adopted or discarded;
 * the remaining count above always reflects what is still on screen.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()

onMounted(async () => {
  await store.loadDrafts({ silent: store.draftsLoaded })
})
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h2 class="page-title">{{ t('pages.review.title') }}</h2>
      <p class="page-description">{{ t('pages.review.description') }}</p>
    </header>

    <p v-if="store.draftsError !== null" class="review__error">
      {{ store.draftsError }}
      <AppButton variant="secondary" @click="store.loadDrafts()">
        {{ t('review.reload') }}
      </AppButton>
    </p>

    <p v-if="store.draftsLoading" class="review__status">{{ t('review.loading') }}</p>

    <template v-else-if="store.draftCount > 0">
      <p class="review__status">{{ t('review.remaining', { count: store.draftCount }) }}</p>
      <ul class="review__list">
        <li v-for="question in store.drafts" :key="question.id">
          <ReviewQuestionCard :question="question" />
        </li>
      </ul>
    </template>

    <EmptyState
      v-else-if="store.draftsLoaded"
      :title="t('review.emptyTitle')"
      :description="t('review.emptyDescription')"
    >
      <template #actions>
        <RouterLink class="review__link" :to="{ name: 'generate' }">
          {{ t('review.goGenerate') }}
        </RouterLink>
      </template>
    </EmptyState>
  </section>
</template>

<style scoped>
.review__list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 0;
  list-style: none;
}

.review__status {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.review__error {
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

.review__link {
  color: var(--color-accent);
}
</style>
