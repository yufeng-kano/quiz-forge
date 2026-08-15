<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { FillBlankPayload } from '@/api'
import StringListEditor from '@/components/questions/StringListEditor.vue'
import { useAppI18n } from '@/i18n'
import { countFillBlankMarkers } from '@/questions/payload'

/**
 * Editor for `fill_blank`.
 *
 * The backend rejects a payload whose `answers` count differs from the number
 * of `____` markers in the stem, so the two counts are shown while editing and
 * the mismatch is called out before the save is attempted — the 422 still
 * decides, this only stops the user from having to guess what went wrong.
 */
const props = defineProps<{ payload: FillBlankPayload }>()
const emit = defineEmits<{ change: [FillBlankPayload] }>()

const { t } = useAppI18n()

const draft = reactive<FillBlankPayload>({
  stem: props.payload.stem,
  answers: [...props.payload.answers],
})

watch(draft, () => emit('change', { stem: draft.stem, answers: [...draft.answers] }), {
  deep: true,
})

const blankCount = computed(() => countFillBlankMarkers(draft.stem))
const matches = computed(() => blankCount.value === draft.answers.length)

const rowLabels = computed(() =>
  draft.answers.map((_answer, index) => t('questions.fillBlank.blankNo', { no: index + 1 })),
)
</script>

<template>
  <div class="editor-form">
    <label class="form-field">
      <span class="form-label">{{ t('questions.labels.stem') }}</span>
      <textarea v-model="draft.stem" class="form-textarea" rows="3" />
      <span class="form-hint">{{ t('questions.fillBlank.markerHint') }}</span>
    </label>

    <StringListEditor
      v-model="draft.answers"
      :label="t('questions.labels.answers')"
      :row-labels="rowLabels"
    />

    <p v-if="matches" class="form-hint">
      {{
        t('questions.fillBlank.countMatch', {
          blanks: blankCount,
          answers: draft.answers.length,
        })
      }}
    </p>
    <p v-else class="form-error">
      {{
        t('questions.fillBlank.countMismatch', {
          blanks: blankCount,
          answers: draft.answers.length,
        })
      }}
    </p>
  </div>
</template>
