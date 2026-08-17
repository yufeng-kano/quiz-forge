<script setup lang="ts">
import { ref, watch } from 'vue'

import {
  QUESTION_TYPES,
  isQuestionType,
  type QuestionCreateRequest,
  type QuestionListItem,
  type QuestionType,
  type TypedQuestionPayload,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import QuestionPayloadFields from '@/components/questions/QuestionPayloadFields.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { DEFAULT_NEW_QUESTION_TYPE, emptyPayload } from '@/questions/defaults'
import {
  DIFFICULTY_LABEL_KEYS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABEL_KEYS,
} from '@/questions/labels'
import { useQuestionsStore } from '@/stores/questions'
import { useToastsStore } from '@/stores/toasts'

/**
 * 新增題目 — writing a question by hand instead of generating one
 * (docs/decisions/2026-08-15-ux-overhaul-feature-expansion.md F1).
 *
 * The form is the same six type editors the review page edits with
 * (`QuestionPayloadFields`), so a hand-written question is built from exactly
 * the fields its type defines. Nothing is validated here beyond what the
 * editors already show: `POST /api/v1/questions` runs the same
 * discriminated-union validation as every other write, and its 422 is
 * displayed field by field rather than swallowed.
 *
 * A manual question is `approved` by default — the author is the reviewer —
 * and can be saved as a draft instead when it is meant to be revisited.
 */
const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{ close: []; created: [question: QuestionListItem] }>()

const { t } = useAppI18n()
const store = useQuestionsStore()
const toasts = useToastsStore()

const questionType = ref<QuestionType>(DEFAULT_NEW_QUESTION_TYPE)
const difficulty = ref('')
const asDraft = ref(false)
const draft = ref<TypedQuestionPayload>(emptyPayload(DEFAULT_NEW_QUESTION_TYPE))
const submitting = ref(false)
const submitError = ref<string | null>(null)

/**
 * Remounts the editor forms. They copy their payload prop into a local draft
 * on setup and deliberately ignore later prop changes (an inline edit must not
 * be overwritten by a background refresh), so switching type or reopening the
 * dialog has to give them a fresh instance.
 */
const formKey = ref(0)

function reset(type: QuestionType): void {
  questionType.value = type
  draft.value = emptyPayload(type)
  submitError.value = null
  formKey.value += 1
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      difficulty.value = ''
      asDraft.value = false
      reset(DEFAULT_NEW_QUESTION_TYPE)
    }
  },
)

function onTypeChange(event: Event): void {
  const target = event.target
  if (target instanceof HTMLSelectElement && isQuestionType(target.value)) {
    reset(target.value)
  }
}

function onPayloadChange(next: TypedQuestionPayload): void {
  draft.value = next
}

async function onSubmit(): Promise<void> {
  if (submitting.value) {
    return
  }
  const request: QuestionCreateRequest = {
    type: draft.value.type,
    payload: draft.value.payload,
    status: asDraft.value ? 'draft' : 'approved',
  }
  if (difficulty.value !== '') {
    request.difficulty = difficulty.value
  }

  submitting.value = true
  submitError.value = null
  try {
    const created = await store.create(request)
    toasts.success(t('bank.create.created', { id: created.id }))
    emit('created', created)
    emit('close')
  } catch (error) {
    submitError.value = translateApiError(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" size="lg" :title="t('bank.create.title')" @close="emit('close')">
    <form class="create-question" @submit.prevent="onSubmit">
      <div class="create-question__meta">
        <label class="form-field">
          <span class="form-label">{{ t('bank.create.type') }}</span>
          <select class="form-select" :value="questionType" @change="onTypeChange">
            <option v-for="type in QUESTION_TYPES" :key="type" :value="type">
              {{ t(QUESTION_TYPE_LABEL_KEYS[type]) }}
            </option>
          </select>
        </label>

        <label class="form-field">
          <span class="form-label">{{ t('bank.create.difficulty') }}</span>
          <select v-model="difficulty" class="form-select">
            <option value="">{{ t('bank.create.difficultyNone') }}</option>
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

      <QuestionPayloadFields :key="formKey" :typed="draft" @change="onPayloadChange" />

      <label class="create-question__draft">
        <input v-model="asDraft" type="checkbox" />
        <span>{{ t('bank.create.asDraft') }}</span>
      </label>

      <p v-if="submitError !== null" class="form-error">{{ submitError }}</p>
    </form>

    <template #actions>
      <AppButton variant="secondary" :disabled="submitting" @click="emit('close')">
        {{ t('common.cancel') }}
      </AppButton>
      <AppButton :disabled="submitting" @click="onSubmit">
        {{ submitting ? t('bank.create.submitting') : t('bank.create.submit') }}
      </AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.create-question {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.create-question__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: var(--space-3) var(--space-4);
}

.create-question__draft {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}
</style>
