<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'

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
 * Toolbar of the question bank: full-text search, semantic search, and the
 * type, difficulty and category filters.
 *
 * Both text boxes are debounced (`SEARCH_DEBOUNCE_MS`) before they reach the
 * store, so a typed word is one query instead of one per keystroke; the
 * selects apply immediately, since each is a single deliberate choice. The
 * semantic box matters more than the literal one: each of its queries costs an
 * embedding call server-side (docs/question-bank.md 題目向量化與語意搜尋).
 *
 * The two searches are not alternatives — `q` stays the literal hard condition
 * and `similar_to` reorders whatever is left, which is what the hint says.
 *
 * The category filter is two selects because `categories` is a subject/topic
 * hierarchy, but `GET /api/v1/questions` takes a single `category_id` and
 * ingestion only ever classifies a chunk at topic level
 * (`backend.ingestion.pipeline`). The subject select only narrows the topic
 * choices; the topic is what actually filters. That is not explained on the
 * page — standing how-to copy is forbidden
 * (docs/decisions/2026-08-17-compact-headers-and-job-errors.md).
 *
 * The values live in the questions store, so they survive leaving the page.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()
const categoriesStore = useCategoriesStore()

onMounted(async () => {
  await categoriesStore.ensureLoaded()
})

/**
 * A text box bound to one store filter through a debounce.
 *
 * Both search boxes need the same three behaviours — hold the keystrokes,
 * push the trimmed value once, and follow the store back to empty when 清除
 * 篩選 resets it — so the wiring is written once here rather than twice.
 */
function debouncedFilterText(
  currentValue: () => string,
  apply: (value: string) => void,
): Ref<string> {
  const text = ref(currentValue())
  let timer: ReturnType<typeof setTimeout> | null = null

  function clearDebounce(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  watch(text, (value) => {
    clearDebounce()
    timer = setTimeout(() => {
      timer = null
      const trimmed = value.trim()
      if (trimmed !== currentValue()) {
        apply(trimmed)
      }
    }, SEARCH_DEBOUNCE_MS)
  })

  watch(currentValue, (value) => {
    if (value !== text.value.trim()) {
      text.value = value
    }
  })

  onUnmounted(clearDebounce)
  return text
}

const searchText = debouncedFilterText(
  () => store.filters.search,
  (value) => {
    store.setFilters({ ...store.filters, search: value })
  },
)

const similarText = debouncedFilterText(
  () => store.filters.similarTo,
  (value) => {
    store.setFilters({ ...store.filters, similarTo: value })
  },
)

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
  <section class="bank-toolbar">
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

      <label class="form-field bank-toolbar__search">
        <span class="form-label">{{ t('bank.filters.similar') }}</span>
        <input
          v-model="similarText"
          class="form-input"
          type="search"
          :placeholder="t('bank.filters.similarPlaceholder')"
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
      <div class="bank-toolbar__hints">
        <p v-if="categoriesStore.loading" class="form-hint">
          {{ t('bank.filters.loadingCategories') }}
        </p>
        <p v-else-if="categoriesStore.loadError !== null" class="form-error">
          {{ categoriesStore.loadError }}
        </p>

        <p v-if="store.filters.similarTo !== ''" class="form-hint">
          {{ t('bank.filters.similarHint') }}
        </p>
      </div>

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
  padding: var(--space-3) 0;
}

.bank-toolbar__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--space-3) var(--space-4);
}

/* The two search boxes are the toolbar's primary controls, so they get the
   wider cells and the four selects share the rest of the row */
.bank-toolbar__search {
  grid-column: span 2;
  min-width: 12rem;
}

.bank-toolbar__hints {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.bank-toolbar__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-3);
}
</style>
