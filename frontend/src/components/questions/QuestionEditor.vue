<script setup lang="ts">
import { ref } from 'vue'

import type { QuestionListItem, QuestionPayload, TypedQuestionPayload } from '@/api'
import AppButton from '@/components/AppButton.vue'
import QuestionPayloadFields from '@/components/questions/QuestionPayloadFields.vue'
import { useAppI18n } from '@/i18n'
import { toTypedPayload } from '@/questions/payload'

/**
 * Inline editing of one question: the form for its type plus the save/cancel
 * row, so the page above only deals with "the user wants to save this payload"
 * (docs/question-bank.md 審題流程 — 使用者可直接編輯題幹／選項／答案).
 *
 * The form itself is `QuestionPayloadFields`, shared with 新增題目. The draft
 * starts as a copy of the stored payload, so cancelling changes nothing.
 * `saving` and `errorMessage` are the caller's, because it is the one doing the
 * PATCH and the one holding the server's 422.
 */
const props = defineProps<{
  question: QuestionListItem
  saving: boolean
  errorMessage: string | null
}>()

const emit = defineEmits<{ save: [QuestionPayload]; cancel: [] }>()

const { t } = useAppI18n()

const draft = ref<TypedQuestionPayload | null>(toTypedPayload(props.question))

function onChange(next: TypedQuestionPayload): void {
  draft.value = next
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
    <QuestionPayloadFields :typed="draft" @change="onChange" />

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
/* The form takes the place of the rendered question inside the row; a left
   rule is all the separation it needs, the same way the quoted source text is
   marked (docs/frontend.md 設計節制原則 — 分割線優先於面板). */
.question-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-left: var(--space-3);
  border-left: 2px solid var(--color-accent);
}

.question-editor__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
