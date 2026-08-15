<script setup lang="ts">
import { computed } from 'vue'

import type {
  AnalogyPayload,
  ComparisonPayload,
  FillBlankPayload,
  ShortAnswerPayload,
  SingleChoicePayload,
  TrueFalsePayload,
  TypedQuestionPayload,
} from '@/api'
import AnalogyEditor from '@/components/questions/AnalogyEditor.vue'
import ComparisonEditor from '@/components/questions/ComparisonEditor.vue'
import FillBlankEditor from '@/components/questions/FillBlankEditor.vue'
import ShortAnswerEditor from '@/components/questions/ShortAnswerEditor.vue'
import SingleChoiceEditor from '@/components/questions/SingleChoiceEditor.vue'
import TrueFalseEditor from '@/components/questions/TrueFalseEditor.vue'
import { useAppI18n } from '@/i18n'

/**
 * Picks the editing form for a payload's type and re-tags what it emits.
 *
 * It is the editing counterpart of `QuestionDisplay`, and the single place the
 * six type editors are wired up: inline editing on 審題/題庫
 * (`QuestionEditor`) and 新增題目 (`QuestionCreateModal`) both go through it,
 * so a seventh type is added in one place rather than two.
 *
 * `null` means the stored payload does not match its type — the caller is told
 * so instead of being handed a form that cannot save.
 */
const props = defineProps<{ typed: TypedQuestionPayload | null }>()

const emit = defineEmits<{ change: [TypedQuestionPayload] }>()

const { t } = useAppI18n()

/** One narrowing accessor per type, so each form gets a concretely typed payload. */
const comparison = computed(() => (props.typed?.type === 'comparison' ? props.typed.payload : null))
const analogy = computed(() => (props.typed?.type === 'analogy' ? props.typed.payload : null))
const singleChoice = computed(() =>
  props.typed?.type === 'single_choice' ? props.typed.payload : null,
)
const trueFalse = computed(() => (props.typed?.type === 'true_false' ? props.typed.payload : null))
const fillBlank = computed(() => (props.typed?.type === 'fill_blank' ? props.typed.payload : null))
const shortAnswer = computed(() =>
  props.typed?.type === 'short_answer' ? props.typed.payload : null,
)

function onComparisonChange(payload: ComparisonPayload): void {
  emit('change', { type: 'comparison', payload })
}

function onAnalogyChange(payload: AnalogyPayload): void {
  emit('change', { type: 'analogy', payload })
}

function onSingleChoiceChange(payload: SingleChoicePayload): void {
  emit('change', { type: 'single_choice', payload })
}

function onTrueFalseChange(payload: TrueFalsePayload): void {
  emit('change', { type: 'true_false', payload })
}

function onFillBlankChange(payload: FillBlankPayload): void {
  emit('change', { type: 'fill_blank', payload })
}

function onShortAnswerChange(payload: ShortAnswerPayload): void {
  emit('change', { type: 'short_answer', payload })
}
</script>

<template>
  <ComparisonEditor v-if="comparison !== null" :payload="comparison" @change="onComparisonChange" />
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
</template>
