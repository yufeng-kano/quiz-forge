<script setup lang="ts">
import { computed, ref } from 'vue'

import type {
  AnalogyPayload,
  ComparisonPayload,
  FillBlankPayload,
  QuestionListItem,
  QuestionPayload,
  ShortAnswerPayload,
  SingleChoicePayload,
  TrueFalsePayload,
  TypedQuestionPayload,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import AnalogyEditor from '@/components/questions/AnalogyEditor.vue'
import ComparisonEditor from '@/components/questions/ComparisonEditor.vue'
import FillBlankEditor from '@/components/questions/FillBlankEditor.vue'
import ShortAnswerEditor from '@/components/questions/ShortAnswerEditor.vue'
import SingleChoiceEditor from '@/components/questions/SingleChoiceEditor.vue'
import TrueFalseEditor from '@/components/questions/TrueFalseEditor.vue'
import { useAppI18n } from '@/i18n'
import { toTypedPayload } from '@/questions/payload'

/**
 * Inline editing of one question: picks the form for its type and owns the
 * draft, so the page above only deals with "the user wants to save this
 * payload" (docs/question-bank.md 審題流程 — 使用者可直接編輯題幹／選項／答案).
 *
 * The draft starts as a copy of the stored payload, so cancelling changes
 * nothing. `saving` and `errorMessage` are the caller's, because it is the one
 * doing the PATCH and the one holding the server's 422.
 */
const props = defineProps<{
  question: QuestionListItem
  saving: boolean
  errorMessage: string | null
}>()

const emit = defineEmits<{ save: [QuestionPayload]; cancel: [] }>()

const { t } = useAppI18n()

const draft = ref<TypedQuestionPayload | null>(toTypedPayload(props.question))

/** One narrowing accessor per type, so each form gets a concretely typed payload. */
const comparison = computed(() => (draft.value?.type === 'comparison' ? draft.value.payload : null))
const analogy = computed(() => (draft.value?.type === 'analogy' ? draft.value.payload : null))
const singleChoice = computed(() =>
  draft.value?.type === 'single_choice' ? draft.value.payload : null,
)
const trueFalse = computed(() => (draft.value?.type === 'true_false' ? draft.value.payload : null))
const fillBlank = computed(() => (draft.value?.type === 'fill_blank' ? draft.value.payload : null))
const shortAnswer = computed(() =>
  draft.value?.type === 'short_answer' ? draft.value.payload : null,
)

function onComparisonChange(payload: ComparisonPayload): void {
  draft.value = { type: 'comparison', payload }
}

function onAnalogyChange(payload: AnalogyPayload): void {
  draft.value = { type: 'analogy', payload }
}

function onSingleChoiceChange(payload: SingleChoicePayload): void {
  draft.value = { type: 'single_choice', payload }
}

function onTrueFalseChange(payload: TrueFalsePayload): void {
  draft.value = { type: 'true_false', payload }
}

function onFillBlankChange(payload: FillBlankPayload): void {
  draft.value = { type: 'fill_blank', payload }
}

function onShortAnswerChange(payload: ShortAnswerPayload): void {
  draft.value = { type: 'short_answer', payload }
}

function onSave(): void {
  const current = draft.value
  if (current !== null) {
    emit('save', current.payload)
  }
}
</script>

<template>
  <form class="question-editor" @submit.prevent="onSave">
    <ComparisonEditor
      v-if="comparison !== null"
      :payload="comparison"
      @change="onComparisonChange"
    />
    <AnalogyEditor v-else-if="analogy !== null" :payload="analogy" @change="onAnalogyChange" />
    <SingleChoiceEditor
      v-else-if="singleChoice !== null"
      :payload="singleChoice"
      @change="onSingleChoiceChange"
    />
    <TrueFalseEditor
      v-else-if="trueFalse !== null"
      :payload="trueFalse"
      @change="onTrueFalseChange"
    />
    <FillBlankEditor
      v-else-if="fillBlank !== null"
      :payload="fillBlank"
      @change="onFillBlankChange"
    />
    <ShortAnswerEditor
      v-else-if="shortAnswer !== null"
      :payload="shortAnswer"
      @change="onShortAnswerChange"
    />
    <p v-else class="form-error">{{ t('editor.unsupported') }}</p>

    <p v-if="props.errorMessage !== null" class="form-error">{{ props.errorMessage }}</p>

    <div class="question-editor__actions">
      <AppButton type="submit" :disabled="saving || draft === null">
        {{ saving ? t('editor.saving') : t('editor.save') }}
      </AppButton>
      <AppButton variant="secondary" :disabled="saving" @click="emit('cancel')">
        {{ t('editor.cancel') }}
      </AppButton>
    </div>
  </form>
</template>

<style scoped>
.question-editor {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 0.9rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background-soft);
}

.question-editor__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
</style>
