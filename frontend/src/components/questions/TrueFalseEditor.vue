<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { TrueFalsePayload } from '@/api'
import { useAppI18n } from '@/i18n'

/** Editor for `true_false`; the answer is a boolean, so it is two radios. */
const props = defineProps<{ payload: TrueFalsePayload }>()
const emit = defineEmits<{ change: [TrueFalsePayload] }>()

const { t } = useAppI18n()

const draft = reactive<TrueFalsePayload>({
  stem: props.payload.stem,
  answer: props.payload.answer,
  explanation: props.payload.explanation,
})

watch(
  draft,
  () =>
    emit('change', {
      stem: draft.stem,
      answer: draft.answer,
      explanation: draft.explanation === '' ? null : draft.explanation,
    }),
  { deep: true },
)
</script>

<template>
  <div class="editor-form">
    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.stem') }}</span>
      <textarea v-model="draft.stem" class="form-textarea" rows="3" />
    </label>

    <div class="form-field">
      <span class="form-label">{{ t('questions.labels.answer') }}</span>
      <div class="editor-row">
        <label class="editor-radio">
          <input v-model="draft.answer" type="radio" :value="true" />
          <span>{{ t('questions.trueFalse.true') }}</span>
        </label>
        <label class="editor-radio">
          <input v-model="draft.answer" type="radio" :value="false" />
          <span>{{ t('questions.trueFalse.false') }}</span>
        </label>
      </div>
    </div>

    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.explanation') }}</span>
      <textarea v-model="draft.explanation" class="form-textarea" rows="2" />
    </label>
  </div>
</template>
