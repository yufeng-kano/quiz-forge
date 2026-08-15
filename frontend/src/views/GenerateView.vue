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
import CategoryScopeField from '@/components/generate/CategoryScopeField.vue'
import DocumentScopeField from '@/components/generate/DocumentScopeField.vue'
import GenerateItemRows from '@/components/generate/GenerateItemRows.vue'
import GenerationJobRow from '@/components/generate/GenerationJobRow.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { DIFFICULTY_LABEL_KEYS, DIFFICULTY_LEVELS } from '@/questions/labels'
import { useGenerationStore } from '@/stores/generation'
import { useToastsStore } from '@/stores/toasts'

/**
 * 出題 — pick the scope, combine 題型 × 數量 rows, pick a difficulty, queue the
 * job (docs/question-bank.md 出題流程 step 1).
 *
 * Nothing is generated here: the request returns a job id, whose progress is
 * polled by the rows on the right. The scope and the combos are deliberately
 * kept after a submit, since asking for more of the same material is the common
 * next step — the two columns exist for exactly that: the form stays where it
 * is while the jobs it produced report next to it.
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
  <div class="page">
    <PageHeader :title="t('pages.generate.title')" :subtitle="t('pages.generate.description')" />

    <div class="generate">
      <form class="card generate__form" @submit.prevent="onSubmit">
        <section class="generate__block">
          <h2 class="card-title">{{ t('generate.form.scopeTitle') }}</h2>
          <p class="form-hint">{{ t('generate.form.scopeHint') }}</p>

          <div class="generate__scope">
            <DocumentScopeField v-model="documentIds" />
            <CategoryScopeField v-model="categoryIds" />
          </div>
        </section>

        <section class="generate__block">
          <h2 class="card-title">{{ t('generate.form.comboTitle') }}</h2>
          <p class="form-hint">{{ t('generate.form.comboHint') }}</p>

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
        <section v-if="store.jobs.length > 0" class="card generate__jobs-card">
          <header class="generate__jobs-head">
            <h2 class="card-title">{{ t('generate.jobs.title') }}</h2>
            <span class="muted-text">{{
              t('generate.jobs.count', { count: store.jobs.length })
            }}</span>
          </header>

          <ul class="generate__jobs-list">
            <li v-for="entry in store.jobs" :key="entry.jobId">
              <GenerationJobRow :entry="entry" />
            </li>
          </ul>
        </section>

        <p v-else class="generate__jobs-empty">{{ t('generate.jobs.empty') }}</p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.generate {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  align-items: start;
  gap: var(--space-4);
}

/* One column as soon as two would make either side too narrow to fill in */
@media (max-width: 1180px) {
  .generate {
    grid-template-columns: minmax(0, 1fr);
  }
}

.generate__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.generate__block {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.generate__scope {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: var(--space-4);
}

.generate__difficulty {
  max-width: 20rem;
}

.generate__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.generate__total {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.generate__jobs-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  /* The column must not grow with the session's history: the card keeps its
     head fixed and the rows scroll inside it (docs/frontend.md 清單有界原則) */
  max-height: calc(100vh - 14rem);
  overflow: hidden;
}

.generate__jobs-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.generate__jobs-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 0;
  overflow-y: auto;
  padding: 0;
  list-style: none;
}

/* Nothing queued yet is one line of guidance, not an empty card the size of
   the form next to it */
.generate__jobs-empty {
  padding: var(--space-3) var(--space-4);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}
</style>
