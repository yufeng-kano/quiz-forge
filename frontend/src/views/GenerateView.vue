<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  GENERATE_COUNT_DEFAULT,
  GENERATE_COUNT_MIN,
  QUESTION_TYPES,
  type GenerateItem,
  type GenerateRequest,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import CategoryScopeField from '@/components/generate/CategoryScopeField.vue'
import DocumentScopeField from '@/components/generate/DocumentScopeField.vue'
import GenerateItemRows from '@/components/generate/GenerateItemRows.vue'
import GenerationJobRow from '@/components/generate/GenerationJobRow.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { DIFFICULTY_LABEL_KEYS, DIFFICULTY_LEVELS } from '@/questions/labels'
import { useGenerationStore } from '@/stores/generation'
import { useToastsStore } from '@/stores/toasts'

/**
 * 出題 — pick the scope, combine 題型 × 數量 rows, pick a difficulty, queue the
 * job (docs/question-bank.md 出題流程 step 1).
 *
 * A split workspace (docs/decisions/2026-08-17-professional-form-pages.md D26):
 * the form on the left in two titled sections, the session's jobs in a rail on
 * the right with its own header and scrollbar. The scope and the combos are
 * deliberately kept after a submit, since asking for more of the same material
 * is the common next step — the form stays where it is while the jobs it
 * produced report next to it.
 *
 * `difficulty` is free text on the backend and goes straight into the prompt,
 * so the option values are the localised level names themselves — see
 * `src/questions/labels.ts`.
 */
const { t } = useAppI18n()
const store = useGenerationStore()
const toasts = useToastsStore()

const documentIds = ref<number[]>([])
const categoryIds = ref<number[]>([])
const items = ref<GenerateItem[]>([
  { question_type: QUESTION_TYPES[0], count: GENERATE_COUNT_DEFAULT },
])
const difficulty = ref('')

const submitting = ref(false)
const submitError = ref<string | null>(null)

const hasScope = computed(() => documentIds.value.length > 0 || categoryIds.value.length > 0)

/** What the job's progress will count, and what the user is billed for. */
const totalCount = computed(() => items.value.reduce((total, item) => total + item.count, 0))

/** Mirrors `GenerateIn`: a scope, at least one item, and every count positive. */
const canSubmit = computed(
  () =>
    hasScope.value &&
    items.value.length > 0 &&
    items.value.every((item) => item.count >= GENERATE_COUNT_MIN) &&
    !submitting.value,
)

async function onSubmit(): Promise<void> {
  if (!canSubmit.value) {
    return
  }
  const request: GenerateRequest = {
    items: items.value.map((item) => ({ ...item })),
  }
  if (documentIds.value.length > 0) {
    request.document_ids = [...documentIds.value]
  }
  if (categoryIds.value.length > 0) {
    request.category_ids = [...categoryIds.value]
  }
  if (difficulty.value !== '') {
    request.difficulty = difficulty.value
  }

  submitting.value = true
  submitError.value = null
  try {
    const entry = await store.submit(request)
    toasts.success(t('generate.form.queued', { id: entry.jobId }))
  } catch (error) {
    const message = translateApiError(error)
    submitError.value = message
    toasts.error(message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page page--workspace generate-page">
    <PageHeader :page-name="t('nav.generate')" />

    <div class="generate">
      <form class="generate__form" @submit.prevent="onSubmit">
        <section class="form-section">
          <h2 class="form-section__title">{{ t('generate.sections.scope') }}</h2>
          <div class="generate__scope">
            <DocumentScopeField v-model="documentIds" />
            <CategoryScopeField v-model="categoryIds" />
          </div>
        </section>

        <section class="form-section">
          <h2 class="form-section__title">{{ t('generate.sections.settings') }}</h2>

          <GenerateItemRows v-model="items" />

          <label class="form-field generate__difficulty">
            <span class="form-label">{{ t('generate.form.difficulty') }}</span>
            <select v-model="difficulty" class="form-select">
              <option value="">{{ t('generate.form.difficultyAny') }}</option>
              <option
                v-for="level in DIFFICULTY_LEVELS"
                :key="level"
                :value="t(DIFFICULTY_LABEL_KEYS[level])"
              >
                {{ t(DIFFICULTY_LABEL_KEYS[level]) }}
              </option>
            </select>
          </label>
        </section>

        <p v-if="submitError !== null" class="form-error">{{ submitError }}</p>

        <div class="generate__actions">
          <AppButton type="submit" :disabled="!canSubmit">
            {{ submitting ? t('generate.form.submitting') : t('generate.form.submit') }}
          </AppButton>
          <span class="generate__total">
            {{ t('generate.form.total', { count: totalCount, calls: totalCount }) }}
          </span>
        </div>
      </form>

      <aside class="generate__jobs">
        <header class="generate__jobs-head">
          <h2 class="generate__jobs-title">{{ t('generate.jobs.title') }}</h2>
          <span v-if="store.jobs.length > 0" class="muted-text">
            {{ t('generate.jobs.count', { count: formatCount(store.jobs.length) }) }}
          </span>
        </header>

        <div
          class="generate__jobs-body"
          :class="{ 'generate__jobs-body--empty': store.jobs.length === 0 }"
        >
          <ul v-if="store.jobs.length > 0" class="generate__jobs-list">
            <li v-for="entry in store.jobs" :key="entry.jobId" class="generate__jobs-item">
              <GenerationJobRow :entry="entry" />
            </li>
          </ul>

          <EmptyState v-else :title="t('generate.jobs.empty')" />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* Two regions of one work surface: the form column and the jobs rail, split by
   the rail's left rule — the same vocabulary as the 題庫 columns (D26). */
.generate {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) 24rem;
  grid-template-rows: minmax(0, 1fr);
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* The form owns the left column's scrollbar and keeps a readable line length:
   fields size to their expected content instead of the whole column (D28). */
.generate__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
  min-height: 0;
  max-width: 44rem;
  overflow-y: auto;
  padding: var(--space-5) var(--space-6) var(--space-7) 0;
}

.generate__scope {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: var(--space-4);
}

.generate__difficulty {
  max-width: 16rem;
}

/* The submit row closes the form the way a dialog footer closes a dialog */
.generate__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-4);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-hairline);
}

/* What the job will produce and what it will cost: read it at full size */
.generate__total {
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

/* The session's jobs are a rail with its own header and its own scrollbar, so
   the list never grows the page (獨立區域各自捲動 / 清單有界原則). */
.generate__jobs {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  padding-left: var(--space-5);
  border-left: 1px solid var(--color-border);
}

.generate__jobs-head {
  flex: none;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-3);
  padding: var(--space-4) 0 var(--space-3);
  border-bottom: 1px solid var(--color-hairline);
}

.generate__jobs-title {
  font-size: var(--font-size-md);
  font-weight: 600;
}

.generate__jobs-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

/* Nothing yet: the one line sits in the middle of the rail, not in a corner */
.generate__jobs-body--empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.generate__jobs-list {
  display: flex;
  flex-direction: column;
  padding: var(--space-3) 0;
  list-style: none;
}

.generate__jobs-item {
  padding: var(--space-4) 0;
}

.generate__jobs-item:first-child {
  padding-top: var(--space-1);
}

.generate__jobs-item + .generate__jobs-item {
  border-top: 1px solid var(--color-hairline);
}

/* Stacked: the workspace clipping is turned off so the page scrolls naturally,
   and the rail follows the form behind a horizontal rule instead of a column */
@media (max-width: 960px) {
  .page.generate-page {
    overflow-y: auto;
  }

  .generate {
    display: flex;
    flex-direction: column;
    height: auto;
    overflow: visible;
  }

  .generate__form {
    max-width: none;
    overflow: visible;
    padding-right: 0;
  }

  .generate__jobs {
    height: auto;
    margin-top: var(--space-5);
    padding-left: 0;
    border-left: none;
    border-top: 1px solid var(--color-border);
  }

  .generate__jobs-body {
    overflow: visible;
  }
}
</style>
