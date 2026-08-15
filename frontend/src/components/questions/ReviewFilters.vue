<script setup lang="ts">
import { computed } from 'vue'

import { QUESTION_TYPES, isQuestionType } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import {
  DIFFICULTY_LABEL_KEYS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABEL_KEYS,
} from '@/questions/labels'
import { useQuestionsStore } from '@/stores/questions'

/**
 * Toolbar of the review queue: type and difficulty.
 *
 * A draft carries no category of its own, so the bank's category filter has no
 * counterpart here — narrowing the queue means "review all the 單選題 first",
 * which these two do. Both go to the server as query parameters, so the
 * remaining count and the pages stay consistent with what is on screen.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()

const questionType = computed<string>({
  get: () => store.draftFilters.type ?? '',
  set: (value) => {
    store.setDraftFilters({
      ...store.draftFilters,
      type: isQuestionType(value) ? value : null,
    })
  },
})

const difficulty = computed<string>({
  get: () => store.draftFilters.difficulty ?? '',
  set: (value) => {
    store.setDraftFilters({ ...store.draftFilters, difficulty: value === '' ? null : value })
  },
})
</script>

<template>
  <section class="card review-toolbar">
    <label class="form-field">
      <span class="form-label">{{ t('bank.filters.type') }}</span>
      <select v-model="questionType" class="form-select">
        <option value="">{{ t('bank.filters.anyType') }}</option>
        <option v-for="type in QUESTION_TYPES" :key="type" :value="type">
          {{ t(QUESTION_TYPE_LABEL_KEYS[type]) }}
        </option>
      </select>
    </label>

    <label class="form-field">
      <span class="form-label">{{ t('bank.filters.difficulty') }}</span>
      <select v-model="difficulty" class="form-select">
        <option value="">{{ t('bank.filters.anyDifficulty') }}</option>
        <option
          v-for="level in DIFFICULTY_LEVELS"
          :key="level"
          :value="t(DIFFICULTY_LABEL_KEYS[level])"
        >
          {{ t(DIFFICULTY_LABEL_KEYS[level]) }}
        </option>
      </select>
    </label>

    <AppButton
      v-if="store.hasActiveDraftFilter"
      variant="secondary"
      size="sm"
      class="review-toolbar__reset"
      @click="store.resetDraftFilters()"
    >
      {{ t('bank.filters.reset') }}
    </AppButton>
  </section>
</template>

<style scoped>
.review-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3) var(--space-4);
}

.review-toolbar .form-field {
  min-width: 11rem;
}

.review-toolbar__reset {
  margin-bottom: 0.15rem;
}
</style>
