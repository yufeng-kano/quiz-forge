<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import type { AnalogyPayload } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { optionLetter } from '@/questions/options'

/**
 * Editor for `analogy`.
 *
 * There is no stem to edit — it is composed from the a/b/c slots — so the form
 * is the four slots plus the optional option list.
 *
 * When options are offered the backend requires the answer to be one of them,
 * so the answer is selected by radio and tracked as an *index*: editing the
 * text of the selected option then keeps it the answer instead of silently
 * turning the payload invalid. Turning options off keeps the answer text and
 * makes the question a blank to fill in again.
 */
const props = defineProps<{ payload: AnalogyPayload }>()
const emit = defineEmits<{ change: [AnalogyPayload] }>()

const { t } = useAppI18n()

const draft = reactive<AnalogyPayload>({
  a: props.payload.a,
  b: props.payload.b,
  c: props.payload.c,
  answer: props.payload.answer,
  options: props.payload.options === null ? null : [...props.payload.options],
  explanation: props.payload.explanation,
})

/** Which option is the answer; meaningless while `options` is null. */
const answerIndex = ref(
  props.payload.options === null
    ? 0
    : Math.max(0, props.payload.options.indexOf(props.payload.answer)),
)

function snapshot(): AnalogyPayload {
  const options = draft.options === null ? null : [...draft.options]
  const selected = options === null ? undefined : options[answerIndex.value]
  return {
    a: draft.a,
    b: draft.b,
    c: draft.c,
    answer: selected ?? draft.answer,
    options,
    explanation: draft.explanation === '' ? null : draft.explanation,
  }
}

watch([draft, answerIndex], () => emit('change', snapshot()), { deep: true })

function toggleOptions(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) {
    return
  }
  if (target.checked) {
    // Start from the existing answer so the required "answer is one of the
    // options" relation holds from the first render.
    draft.options = [draft.answer, '']
    answerIndex.value = 0
    return
  }
  const selected = draft.options?.[answerIndex.value]
  if (selected !== undefined && selected !== '') {
    draft.answer = selected
  }
  draft.options = null
}

function updateOption(index: number, event: Event): void {
  const target = event.target
  if (target instanceof HTMLInputElement && draft.options !== null) {
    draft.options.splice(index, 1, target.value)
  }
}

function removeOption(index: number): void {
  if (draft.options === null) {
    return
  }
  const previous = answerIndex.value
  draft.options.splice(index, 1)
  if (index < previous) {
    answerIndex.value = previous - 1
  }
  if (answerIndex.value > draft.options.length - 1) {
    answerIndex.value = Math.max(0, draft.options.length - 1)
  }
}

function addOption(): void {
  draft.options?.push('')
}
</script>

<template>
  <div class="editor-form">
    <label class="form-field">
      <span class="form-label">{{ t('questions.analogy.slotA') }}</span>
      <input v-model="draft.a" class="form-input" type="text" />
    </label>

    <label class="form-field">
      <span class="form-label">{{ t('questions.analogy.slotB') }}</span>
      <input v-model="draft.b" class="form-input" type="text" />
    </label>

    <label class="form-field">
      <span class="form-label">{{ t('questions.analogy.slotC') }}</span>
      <input v-model="draft.c" class="form-input" type="text" />
    </label>

    <label v-if="draft.options === null" class="form-field">
      <span class="form-label">{{ t('questions.labels.answer') }}</span>
      <input v-model="draft.answer" class="form-input" type="text" />
    </label>

    <label class="editor-radio">
      <input type="checkbox" :checked="draft.options !== null" @change="toggleOptions" />
      <span>{{ t('questions.analogy.withOptions') }}</span>
    </label>

    <div v-if="draft.options !== null" class="form-field">
      <span class="form-label">{{ t('questions.labels.options') }}</span>
      <div v-for="(option, index) in draft.options" :key="index" class="editor-row analogy__option">
        <label class="editor-radio">
          <input v-model="answerIndex" type="radio" :value="index" />
          <span class="analogy__marker">
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
.analogy__option {
  align-items: center;
}

.analogy__marker {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}
</style>
