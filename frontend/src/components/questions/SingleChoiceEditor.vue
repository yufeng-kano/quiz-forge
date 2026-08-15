<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { SingleChoicePayload } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { optionLetter } from '@/questions/options'

/**
 * Editor for `single_choice`.
 *
 * The answer is picked with a radio on the option itself instead of a separate
 * index field: `answer_index` must point inside `options`, and typing a number
 * by hand is the easiest way to get that wrong. Removing an option therefore
 * moves the selection with it rather than leaving it dangling.
 *
 * The draft is local and the parent is notified of every change, so cancelling
 * an edit only means dropping this component.
 */
const props = defineProps<{ payload: SingleChoicePayload }>()
const emit = defineEmits<{ change: [SingleChoicePayload] }>()

const { t } = useAppI18n()

const draft = reactive<SingleChoicePayload>({
  stem: props.payload.stem,
  options: [...props.payload.options],
  answer_index: props.payload.answer_index,
  explanation: props.payload.explanation,
})

function snapshot(): SingleChoicePayload {
  return {
    stem: draft.stem,
    options: [...draft.options],
    answer_index: draft.answer_index,
    explanation: draft.explanation === '' ? null : draft.explanation,
  }
}

watch(draft, () => emit('change', snapshot()), { deep: true })

function updateOption(index: number, event: Event): void {
  const target = event.target
  if (target instanceof HTMLInputElement) {
    draft.options.splice(index, 1, target.value)
  }
}

function removeOption(index: number): void {
  const previousAnswer = draft.answer_index
  draft.options.splice(index, 1)
  if (index < previousAnswer) {
    draft.answer_index = previousAnswer - 1
  }
  if (draft.answer_index > draft.options.length - 1) {
    draft.answer_index = Math.max(0, draft.options.length - 1)
  }
}

function addOption(): void {
  draft.options.push('')
}
</script>

<template>
  <div class="editor-form">
    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.stem') }}</span>
      <textarea v-model="draft.stem" class="form-textarea" rows="3" />
    </label>

    <div class="form-field">
      <span class="form-label">{{ t('questions.labels.options') }}</span>
      <div v-for="(option, index) in draft.options" :key="index" class="editor-row editor__option">
        <label class="editor-radio">
          <input v-model="draft.answer_index" type="radio" :value="index" />
          <span class="editor__marker">
            {{ t('questions.option.marker', { letter: optionLetter(index) }) }}
          </span>
        </label>
        <input
          class="form-input"
          type="text"
          :value="option"
          @input="updateOption(index, $event)"
        />
        <button type="button" class="editor-remove" @click="removeOption(index)">
          {{ t('editor.remove') }}
        </button>
      </div>
      <p class="form-hint">{{ t('editor.markCorrect') }}</p>
      <div>
        <AppButton variant="secondary" @click="addOption">{{ t('editor.addOption') }}</AppButton>
      </div>
    </div>

    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.explanation') }}</span>
      <textarea v-model="draft.explanation" class="form-textarea" rows="2" />
    </label>
  </div>
</template>

<style scoped>
.editor__option {
  align-items: center;
}

.editor__marker {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}
</style>
