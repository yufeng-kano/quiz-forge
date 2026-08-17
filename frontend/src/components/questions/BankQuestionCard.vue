<script setup lang="ts">
import { computed, ref } from 'vue'

import type { QuestionListItem } from '@/api'
import AppButton from '@/components/AppButton.vue'
import QuestionCard from '@/components/questions/QuestionCard.vue'
import QuestionDisplay from '@/components/questions/QuestionDisplay.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
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
 *
 * 複製 / 丟棄 are icon-only: they are secondary next to the checkbox
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D12). Review keeps
 * labelled 採用／丟棄／編輯 buttons.
 *
 * Every row here is `approved`, so the card only shows a status when one is
 * not (docs/frontend.md 設計節制原則 — 不重述外框已經說過的事).
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
  <QuestionCard :question="question" expected-status="approved">
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
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :disabled="acting !== null"
        :aria-label="t('bank.duplicateAria', { id: question.id })"
        :title="t('bank.duplicateAria', { id: question.id })"
        @click="onDuplicate"
      >
        <AppIcon name="duplicate" :size="16" />
      </AppButton>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :disabled="acting !== null"
        :aria-label="t('bank.rejectAria', { id: question.id })"
        :title="t('bank.rejectAria', { id: question.id })"
        @click="onReject"
      >
        <AppIcon name="trash" :size="16" />
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
