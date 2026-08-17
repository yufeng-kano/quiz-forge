<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'
import {
  isEmptySearchFilters,
  parseAgentSteps,
  type BankAgentSearchFilters,
  type BankAgentStep,
} from '@/questions/agentSteps'
import { QUESTION_TYPE_LABEL_KEYS } from '@/questions/labels'
import { useCategoriesStore } from '@/stores/categories'
import { useQuestionsStore } from '@/stores/questions'
import { useToastsStore } from '@/stores/toasts'

/**
 * 「查詢過程」 of one turn: what the agent actually searched for and how much
 * it found (docs/decisions/2026-08-17-bank-agent-semantic-selection.md D6 —
 * 讓選題不是黑箱).
 *
 * Collapsed by default and scrolling inside its own bounded box, so a turn
 * that took six steps does not push the conversation off screen
 * (docs/frontend.md 清單有界原則).
 *
 * 套用到篩選 writes one search step's conditions into the bank filters. The
 * person is already on 題庫, so this does not navigate
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D10).
 */
const props = defineProps<{ steps: readonly unknown[] | null }>()

const { t } = useAppI18n()
const questions = useQuestionsStore()
const categories = useCategoriesStore()
const toasts = useToastsStore()

const expanded = ref(false)

onMounted(async () => {
  // Category names are needed to say 分類：三角函數 rather than 分類 #12.
  await categories.ensureLoaded()
})

const parsed = computed<BankAgentStep[]>(() => parseAgentSteps(props.steps))

function categoryName(categoryId: number): string {
  const category = categories.categories.find((candidate) => candidate.id === categoryId)
  return category?.name ?? t('bankAgent.steps.filterCategoryUnknown', { id: categoryId })
}

/**
 * One search step's conditions as plain lines, in the order they narrow.
 *
 * These are open-ended values — a semantic query is a whole sentence, a
 * category is a user-visible name — so they are text, never pills: a pill
 * cannot wrap and its border would cut through the word in this narrow column
 * (docs/decisions/2026-08-17-ui-design-restraint.md D17).
 */
function filterLines(filters: BankAgentSearchFilters): string[] {
  if (isEmptySearchFilters(filters)) {
    return [t('bankAgent.steps.noFilters')]
  }
  const lines: string[] = []
  if (filters.similarTo !== null) {
    lines.push(t('bankAgent.steps.filterSimilarTo', { value: filters.similarTo }))
  }
  if (filters.q !== null) {
    lines.push(t('bankAgent.steps.filterQ', { value: filters.q }))
  }
  if (filters.type !== null) {
    lines.push(
      t('bankAgent.steps.filterType', { value: t(QUESTION_TYPE_LABEL_KEYS[filters.type]) }),
    )
  }
  if (filters.difficulty !== null) {
    lines.push(t('bankAgent.steps.filterDifficulty', { value: filters.difficulty }))
  }
  if (filters.categoryId !== null) {
    lines.push(t('bankAgent.steps.filterCategory', { value: categoryName(filters.categoryId) }))
  }
  return lines
}

/**
 * Put a step's conditions into the bank's filters. The person is already on
 * 題庫, so this does not change the route.
 *
 * `limit` is deliberately not carried over: it was how many hits the agent
 * asked to see in one step, not a filter, and the bank has its own paging.
 * A category id that is a subject rather than a topic sets both selects to it,
 * so the filter bar shows what is actually being filtered on.
 */
function onApply(filters: BankAgentSearchFilters): void {
  const category =
    filters.categoryId === null
      ? null
      : (categories.categories.find((candidate) => candidate.id === filters.categoryId) ?? null)
  questions.setFilters({
    type: filters.type,
    difficulty: filters.difficulty,
    subjectId: category === null ? null : (category.parent_id ?? category.id),
    categoryId: filters.categoryId,
    search: filters.q ?? '',
    similarTo: filters.similarTo ?? '',
  })
  toasts.success(t('bankAgent.steps.applied'))
}
</script>

<template>
  <section v-if="parsed.length > 0" class="steps">
    <button
      class="steps__toggle"
      type="button"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <AppIcon :name="expanded ? 'chevronUp' : 'chevronDown'" :size="14" />
      <span>
        {{
          expanded ? t('bankAgent.steps.hide') : t('bankAgent.steps.show', { count: parsed.length })
        }}
      </span>
    </button>

    <ol v-if="expanded" class="steps__list">
      <li v-for="step in parsed" :key="step.step" class="steps__item">
        <template v-if="step.action === 'search'">
          <p class="steps__title">
            {{ t('bankAgent.steps.searchTitle', { step: step.step, count: step.hitCount }) }}
          </p>
          <ul class="steps__filters">
            <li
              v-for="line in filterLines(step.filters)"
              :key="line"
              class="steps__filter text-ellipsis"
              :title="line"
            >
              {{ line }}
            </li>
          </ul>
          <AppButton size="sm" variant="ghost" @click="onApply(step.filters)">
            {{ t('bankAgent.steps.apply') }}
          </AppButton>
        </template>

        <p v-else-if="step.action === 'propose'" class="steps__title">
          {{
            t('bankAgent.steps.proposeTitle', {
              step: step.step,
              count: step.questionIds.length,
            })
          }}
        </p>

        <p v-else class="steps__title">
          {{ t('bankAgent.steps.replyTitle', { step: step.step }) }}
        </p>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.steps {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.steps__toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  color: var(--color-text-muted);
  font: inherit;
  font-size: var(--font-size-md);
  cursor: pointer;
}

.steps__toggle:hover {
  color: var(--color-heading);
}

/* The log grows with the turn's step count, so it scrolls inside itself */
.steps__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 12rem;
  overflow-y: auto;
  margin: 0;
  padding: 0;
  list-style: none;
}

.steps__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.steps__item:last-child {
  border-bottom: none;
}

.steps__title {
  color: var(--color-heading);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.steps__filters {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-width: 100%;
  padding: 0;
  list-style: none;
}

/* A semantic query can be a whole sentence: one line, full text in the tooltip */
.steps__filter {
  max-width: 100%;
  color: var(--color-text);
  font-size: var(--font-size-md);
}
</style>
