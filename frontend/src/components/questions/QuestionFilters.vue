<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { QUESTION_TYPES, SEARCH_DEBOUNCE_MS, isQuestionType, type Category } from '@/api'
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
 * Toolbar of the question bank: full-text search plus the type, difficulty and
 * category filters.
 *
 * Typing is debounced (`SEARCH_DEBOUNCE_MS`) before it reaches the store, so a
 * typed word is one query instead of one per keystroke; the selects apply
 * immediately, since each is a single deliberate choice.
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

const searchText = ref(store.filters.search)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function clearDebounce(): void {
  if (debounceTimer !== null) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
}

watch(searchText, (value) => {
  clearDebounce()
  debounceTimer = setTimeout(() => {
    debounceTimer = null
    const trimmed = value.trim()
    if (trimmed !== store.filters.search) {
      store.setFilters({ ...store.filters, search: trimmed })
    }
  }, SEARCH_DEBOUNCE_MS)
})

// 清除篩選 resets the store, and the box has to follow it back to empty.
watch(
  () => store.filters.search,
  (value) => {
    if (value !== searchText.value.trim()) {
      searchText.value = value
    }
  },
)

onUnmounted(clearDebounce)

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
  <section class="card bank-toolbar">
    <div class="bank-toolbar__fields">
      <label class="form-field bank-toolbar__search">
        <span class="form-label">{{ t('bank.filters.search') }}</span>
        <input
          v-model="searchText"
          class="form-input"
          type="search"
          :placeholder="t('bank.filters.searchPlaceholder')"
        />
      </label>

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

    <div class="bank-toolbar__footer">
      <p v-if="categoriesStore.loading" class="form-hint">
        {{ t('bank.filters.loadingCategories') }}
      </p>
      <p v-else-if="categoriesStore.loadError !== null" class="form-error">
        {{ categoriesStore.loadError }}
      </p>
      <p v-else class="form-hint">{{ t('bank.filters.topicHint') }}</p>

      <AppButton
        v-if="store.hasActiveFilter"
        variant="secondary"
        size="sm"
        @click="store.resetFilters()"
      >
        {{ t('bank.filters.reset') }}
      </AppButton>
    </div>
  </section>
</template>

<style scoped>
.bank-toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.bank-toolbar__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--space-3) var(--space-4);
}

/* The search box is the toolbar's primary control, so it gets the wider cell */
.bank-toolbar__search {
  grid-column: span 2;
  min-width: 12rem;
}

.bank-toolbar__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-3);
}
</style>
