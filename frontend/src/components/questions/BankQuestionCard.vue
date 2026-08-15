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

/**
 * One approved question in the bank: the same rendering as the review page,
 * plus the export checkbox and a way to take a mistake back out
 * (`reject`, docs/question-bank.md 狀態機 — `approved -> rejected`).
 *
 * A discarded question also leaves the export selection: keeping its id there
 * would queue a question the export range no longer contains.
 */
const props = defineProps<{ question: QuestionListItem }>()

const { t } = useAppI18n()
const store = useQuestionsStore()
const selection = useExportSelectionStore()

const rejecting = ref(false)
const actionError = ref<string | null>(null)

const selected = computed(() => selection.isSelected(props.question.id))

async function onReject(): Promise<void> {
  rejecting.value = true
  actionError.value = null
  try {
    await store.reject(props.question.id)
    selection.deselect(props.question.id)
  } catch (error) {
    actionError.value = translateApiError(error)
  } finally {
    rejecting.value = false
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
      <AppButton variant="secondary" :disabled="rejecting" @click="onReject">
        {{ rejecting ? t('bank.rejecting') : t('bank.reject') }}
      </AppButton>
    </template>

    <QuestionDisplay :question="question" />

    <template #footer>
      <p v-if="actionError !== null" class="form-error">{{ actionError }}</p>
    </template>
  </QuestionCard>
</template>

<style scoped>
.bank-card__checkbox {
  width: 1.05rem;
  height: 1.05rem;
  cursor: pointer;
}
</style>
