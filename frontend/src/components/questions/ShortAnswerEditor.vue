<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { ShortAnswerPayload } from '@/api'
import StringListEditor from '@/components/questions/StringListEditor.vue'
import { useAppI18n } from '@/i18n'

/** Editor for `short_answer`; `key_points` is the grading checklist. */
const props = defineProps<{ payload: ShortAnswerPayload }>()
const emit = defineEmits<{ change: [ShortAnswerPayload] }>()

const { t } = useAppI18n()

const draft = reactive<ShortAnswerPayload>({
  stem: props.payload.stem,
  model_answer: props.payload.model_answer,
  key_points: [...props.payload.key_points],
})

watch(
  draft,
  () =>
    emit('change', {
      stem: draft.stem,
      model_answer: draft.model_answer,
      key_points: [...draft.key_points],
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

    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.modelAnswer') }}</span>
      <textarea v-model="draft.model_answer" class="form-textarea" rows="4" />
    </label>

    <StringListEditor
      v-model="draft.key_points"
      :label="t('questions.labels.keyPoints')"
      multiline
    />
  </div>
</template>
