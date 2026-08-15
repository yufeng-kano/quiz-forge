<script setup lang="ts">
import { computed, ref } from 'vue'

import type { QuestionListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import QuestionCard from '@/components/questions/QuestionCard.vue'
import QuestionDisplay from '@/components/questions/QuestionDisplay.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useExportSelectionStore } from '@/stores/exportSelection'
import { useQuestionsStore } from '@/stores/questions'
import { useToastsStore } from '@/stores/toasts'

/**
 * One approved question in the bank: the same rendering as the review page,
 * plus the export checkbox, a copy action and a way to take a mistake back out
 * (`reject`, docs/question-bank.md 狀態機 — `approved -> rejected`).
 *
 * A discarded question also leaves the export selection: keeping its id there
 * would queue a question the export range no longer contains.
 *
 * 複製 creates a `draft` copy (docs/…-ux-overhaul-feature-expansion.md F1), so
 * the copy is not in the bank — the toast says where it went instead of
 * leaving the user looking for it here.
 */
const props = defineProps<{ question: QuestionListItem }>()

const emit = defineEmits<{ duplicated: [question: QuestionListItem] }>()

const { t } = useAppI18n()
const store = useQuestionsStore()
const selection = useExportSelectionStore()
const toasts = useToastsStore()

const acting = ref<'reject' | 'duplicate' | null>(null)

const selected = computed(() => selection.isSelected(props.question.id))

async function onReject(): Promise<void> {
  acting.value = 'reject'
  try {
    await store.reject(props.question.id)
    selection.deselect(props.question.id)
    toasts.success(t('bank.rejected', { id: props.question.id }))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    acting.value = null
  }
}

async function onDuplicate(): Promise<void> {
  acting.value = 'duplicate'
  try {
    const copy = await store.duplicate(props.question.id)
    toasts.success(t('bank.duplicated', { id: copy.id }))
    emit('duplicated', copy)
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    acting.value = null
  }
}
</script>

<template>
  <QuestionCard :question="question">
    <template #select>
      <input
        type="checkbox"
        class="bank-card__checkbox"
        :checked="selected"
        :aria-label="t('bank.selection.checkbox', { id: question.id })"
        @change="selection.toggle(question.id)"
      />
    </template>

    <template #actions>
      <AppButton variant="secondary" size="sm" :disabled="acting !== null" @click="onDuplicate">
        {{ acting === 'duplicate' ? t('bank.duplicating') : t('bank.duplicate') }}
      </AppButton>
      <AppButton variant="secondary" size="sm" :disabled="acting !== null" @click="onReject">
        {{ acting === 'reject' ? t('bank.rejecting') : t('bank.reject') }}
      </AppButton>
    </template>

    <QuestionDisplay :question="question" />
  </QuestionCard>
</template>

<style scoped>
.bank-card__checkbox {
  width: 1.05rem;
  height: 1.05rem;
  cursor: pointer;
}
</style>
