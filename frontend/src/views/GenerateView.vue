<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  GENERATE_COUNT_DEFAULT,
  GENERATE_COUNT_MAX,
  GENERATE_COUNT_MIN,
  QUESTION_TYPES,
  type GenerateRequest,
  type QuestionType,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import CategoryScopePicker from '@/components/generate/CategoryScopePicker.vue'
import DocumentScopePicker from '@/components/generate/DocumentScopePicker.vue'
import GenerationJobRow from '@/components/generate/GenerationJobRow.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import {
  DIFFICULTY_LABEL_KEYS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABEL_KEYS,
} from '@/questions/labels'
import { useGenerationStore } from '@/stores/generation'
import { useToastsStore } from '@/stores/toasts'

/**
 * 出題 — pick the scope, type, count and difficulty, then queue the job
 * (docs/question-bank.md 出題流程 step 1).
 *
 * Nothing is generated here: the request returns a job id, whose progress is
 * polled by the rows on the right. The scope selection is deliberately kept
 * after a submit, since asking for more of the same material is the common
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
const questionType = ref<QuestionType>(QUESTION_TYPES[0])
const count = ref(GENERATE_COUNT_DEFAULT)
const difficulty = ref('')

const submitting = ref(false)
const submitError = ref<string | null>(null)

const hasScope = computed(() => documentIds.value.length > 0 || categoryIds.value.length > 0)

function onCountInput(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) {
    return
  }
  const parsed = Number.parseInt(target.value, 10)
  if (Number.isNaN(parsed)) {
    count.value = GENERATE_COUNT_MIN
    return
  }
  count.value = Math.min(GENERATE_COUNT_MAX, Math.max(GENERATE_COUNT_MIN, parsed))
}

async function onSubmit(): Promise<void> {
  if (!hasScope.value || submitting.value) {
    return
  }
  const request: GenerateRequest = {
    question_type: questionType.value,
    count: count.value,
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
        <h2 class="card-title">{{ t('generate.form.scopeTitle') }}</h2>
        <p class="form-hint">{{ t('generate.form.scopeHint') }}</p>

        <div class="generate__scope">
          <DocumentScopePicker v-model="documentIds" />
          <CategoryScopePicker v-model="categoryIds" />
        </div>

        <div class="generate__settings">
          <label class="form-field">
            <span class="form-label">{{ t('generate.form.type') }}</span>
            <select v-model="questionType" class="form-select">
              <option v-for="type in QUESTION_TYPES" :key="type" :value="type">
                {{ t(QUESTION_TYPE_LABEL_KEYS[type]) }}
              </option>
            </select>
          </label>

          <label class="form-field">
            <span class="form-label">{{ t('generate.form.count') }}</span>
            <input
              class="form-input"
              type="number"
              :min="GENERATE_COUNT_MIN"
              :max="GENERATE_COUNT_MAX"
              :value="count"
              @input="onCountInput"
            />
            <span class="form-hint">
              {{
                t('generate.form.countHint', { min: GENERATE_COUNT_MIN, max: GENERATE_COUNT_MAX })
              }}
            </span>
          </label>

          <label class="form-field">
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
        </div>

        <p v-if="submitError !== null" class="form-error">{{ submitError }}</p>

        <div class="generate__actions">
          <AppButton type="submit" :disabled="!hasScope || submitting">
            {{ submitting ? t('generate.form.submitting') : t('generate.form.submit') }}
          </AppButton>
        </div>
      </form>

      <section class="card generate__jobs">
        <h2 class="card-title">{{ t('generate.jobs.title') }}</h2>
        <p v-if="store.jobs.length === 0" class="form-hint">{{ t('generate.jobs.empty') }}</p>
        <ul v-else class="generate__jobs-list">
          <li v-for="entry in store.jobs" :key="entry.jobId">
            <GenerationJobRow :entry="entry" />
          </li>
        </ul>
      </section>
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

.generate__form,
.generate__jobs {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.generate__scope,
.generate__settings {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--space-4);
}

.generate__actions {
  display: flex;
}

.generate__jobs-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 0;
  list-style: none;
}
</style>
