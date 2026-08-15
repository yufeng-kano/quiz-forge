<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { ComparisonDifference, ComparisonPayload } from '@/api'
import AppButton from '@/components/AppButton.vue'
import StringListEditor from '@/components/questions/StringListEditor.vue'
import { useAppI18n } from '@/i18n'

/**
 * Editor for `comparison`.
 *
 * The model answer is a structure, not text, so the similarities are a list and
 * the differences are edited as the same 面向 × A × B rows the answer sheet
 * prints. The aspect of a row is free text rather than a picker over `aspects`:
 * the backend does not enforce that relation, and forcing it here would make an
 * existing question uneditable whenever the LLM named an aspect slightly
 * differently.
 */
const props = defineProps<{ payload: ComparisonPayload }>()
const emit = defineEmits<{ change: [ComparisonPayload] }>()

const { t } = useAppI18n()

const draft = reactive<ComparisonPayload>({
  stem: props.payload.stem,
  subject_a: props.payload.subject_a,
  subject_b: props.payload.subject_b,
  aspects: [...props.payload.aspects],
  model_answer: {
    similarities: [...props.payload.model_answer.similarities],
    differences: props.payload.model_answer.differences.map((row) => ({ ...row })),
  },
})

function snapshot(): ComparisonPayload {
  return {
    stem: draft.stem,
    subject_a: draft.subject_a,
    subject_b: draft.subject_b,
    aspects: [...draft.aspects],
    model_answer: {
      similarities: [...draft.model_answer.similarities],
      differences: draft.model_answer.differences.map((row) => ({ ...row })),
    },
  }
}

watch(draft, () => emit('change', snapshot()), { deep: true })

function updateDifference(index: number, field: keyof ComparisonDifference, event: Event): void {
  const target = event.target
  const row = draft.model_answer.differences[index]
  if (row !== undefined && target instanceof HTMLInputElement) {
    row[field] = target.value
  }
}

function removeDifference(index: number): void {
  draft.model_answer.differences.splice(index, 1)
}

function addDifference(): void {
  draft.model_answer.differences.push({ aspect: '', a: '', b: '' })
}
</script>

<template>
  <div class="editor-form">
    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.stem') }}</span>
      <textarea v-model="draft.stem" class="form-textarea" rows="3" />
    </label>

    <div class="comparison-editor__subjects">
      <label class="form-field">
        <span class="form-label">{{ t('questions.labels.subjectA') }}</span>
        <input v-model="draft.subject_a" class="form-input" type="text" />
      </label>
      <label class="form-field">
        <span class="form-label">{{ t('questions.labels.subjectB') }}</span>
        <input v-model="draft.subject_b" class="form-input" type="text" />
      </label>
    </div>

    <StringListEditor v-model="draft.aspects" :label="t('questions.labels.aspects')" />

    <StringListEditor
      v-model="draft.model_answer.similarities"
      :label="t('questions.labels.similarities')"
      multiline
    />

    <div class="form-field">
      <span class="form-label">{{ t('questions.labels.differences') }}</span>
      <div
        v-for="(row, index) in draft.model_answer.differences"
        :key="index"
        class="comparison-editor__difference"
      >
        <span class="comparison-editor__row-label">
          {{ t('editor.differenceRow', { no: index + 1 }) }}
        </span>
        <div class="comparison-editor__difference-fields">
          <input
            class="form-input"
            type="text"
            :value="row.aspect"
            :placeholder="t('questions.labels.aspect')"
            @input="updateDifference(index, 'aspect', $event)"
          />
          <input
            class="form-input"
            type="text"
            :value="row.a"
            :placeholder="draft.subject_a"
            @input="updateDifference(index, 'a', $event)"
          />
          <input
            class="form-input"
            type="text"
            :value="row.b"
            :placeholder="draft.subject_b"
            @input="updateDifference(index, 'b', $event)"
          />
        </div>
        <button type="button" class="editor-remove" @click="removeDifference(index)">
          {{ t('editor.remove') }}
        </button>
      </div>
      <div>
        <AppButton variant="secondary" @click="addDifference">
          {{ t('editor.addDifference') }}
        </AppButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.comparison-editor__subjects {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 0.75rem;
}

.comparison-editor__difference {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.comparison-editor__row-label {
  flex: none;
  padding-top: 0.45rem;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  white-space: nowrap;
}

.comparison-editor__difference-fields {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 0.4rem;
  min-width: 0;
}
</style>
