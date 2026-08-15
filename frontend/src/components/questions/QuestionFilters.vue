<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { QUESTION_TYPES, isQuestionType, type Category } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import {
  DIFFICULTY_LABEL_KEYS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABEL_KEYS,
} from '@/questions/labels'
import { useCategoriesStore } from '@/stores/categories'
import { useQuestionsStore } from '@/stores/questions'

/**
 * Filters of the question bank: type, difficulty and category.
 *
 * The category filter is two selects because `categories` is a subject/topic
 * hierarchy, but `GET /api/v1/questions` takes a single `category_id` and
 * ingestion only ever classifies a chunk at topic level
 * (`backend.ingestion.pipeline`). So the subject select narrows the topic
 * choices and the topic is what actually filters — stated in the hint below
 * rather than silently returning nothing for a subject-only choice.
 *
 * The values live in the questions store, so they survive leaving the page.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()
const categoriesStore = useCategoriesStore()

onMounted(async () => {
  await categoriesStore.ensureLoaded()
})

const questionType = computed<string>({
  get: () => store.filters.type ?? '',
  set: (value) => {
    store.setFilters({ ...store.filters, type: isQuestionType(value) ? value : null })
  },
})

const difficulty = computed<string>({
  get: () => store.filters.difficulty ?? '',
  set: (value) => {
    store.setFilters({ ...store.filters, difficulty: value === '' ? null : value })
  },
})

const subjectId = computed<string>({
  get: () => (store.filters.subjectId === null ? '' : String(store.filters.subjectId)),
  set: (value) => {
    // Changing subject drops the topic: a topic under the previous subject
    // would keep filtering while no longer being offered in the select.
    store.setFilters({
      ...store.filters,
      subjectId: value === '' ? null : Number(value),
      categoryId: null,
    })
  },
})

const categoryId = computed<string>({
  get: () => (store.filters.categoryId === null ? '' : String(store.filters.categoryId)),
  set: (value) => {
    store.setFilters({ ...store.filters, categoryId: value === '' ? null : Number(value) })
  },
})

const topics = computed<Category[]>(() => {
  const selected = store.filters.subjectId
  if (selected === null) {
    return []
  }
  const subject = categoriesStore.tree.find((node) => node.category.id === selected)
  return subject?.children ?? []
})
</script>

<template>
  <section class="filters">
    <h3 class="filters__title">{{ t('bank.filters.title') }}</h3>

    <div class="filters__grid">
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

      <label class="form-field">
        <span class="form-label">{{ t('bank.filters.subject') }}</span>
        <select v-model="subjectId" class="form-select">
          <option value="">{{ t('bank.filters.anySubject') }}</option>
          <option
            v-for="node in categoriesStore.tree"
            :key="node.category.id"
            :value="String(node.category.id)"
          >
            {{ node.category.name }}
          </option>
        </select>
      </label>

      <label class="form-field">
        <span class="form-label">{{ t('bank.filters.topic') }}</span>
        <select v-model="categoryId" class="form-select" :disabled="topics.length === 0">
          <option value="">{{ t('bank.filters.anyTopic') }}</option>
          <option v-for="topic in topics" :key="topic.id" :value="String(topic.id)">
            {{ topic.name }}
          </option>
        </select>
      </label>
    </div>

    <p v-if="categoriesStore.loading" class="form-hint">
      {{ t('bank.filters.loadingCategories') }}
    </p>
    <p v-else-if="categoriesStore.loadError !== null" class="form-error">
      {{ categoriesStore.loadError }}
    </p>
    <p class="form-hint">{{ t('bank.filters.topicHint') }}</p>

    <div v-if="store.hasActiveFilter" class="filters__actions">
      <AppButton variant="secondary" @click="store.resetFilters()">
        {{ t('bank.filters.reset') }}
      </AppButton>
    </div>
  </section>
</template>

<style scoped>
.filters {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background-soft);
}

.filters__title {
  font-size: 1rem;
}

.filters__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.75rem 1.25rem;
}

.filters__actions {
  display: flex;
}
</style>
