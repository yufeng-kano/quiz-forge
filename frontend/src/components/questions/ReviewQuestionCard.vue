<script setup lang="ts">
import { ref } from 'vue'

import {
  getQuestion,
  type QuestionDetail,
  type QuestionListItem,
  type QuestionPayload,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import MarkdownContent from '@/components/MarkdownContent.vue'
import QuestionCard from '@/components/questions/QuestionCard.vue'
import QuestionDisplay from '@/components/questions/QuestionDisplay.vue'
import QuestionEditor from '@/components/questions/QuestionEditor.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useQuestionsStore } from '@/stores/questions'

/**
 * One draft question in the review queue: render it, compare it against the
 * source text it was generated from, edit it, then adopt or discard it
 * (docs/question-bank.md 審題流程).
 *
 * Adopting and discarding both go through the store, which puts the *server's*
 * version of the row back into the lists — so the card only leaves the queue
 * once the status change is confirmed, never on optimism alone.
 *
 * The source text comes from `GET /api/v1/questions/{id}` and is fetched the
 * first time it is asked for, not for every card in the list.
 */
const props = defineProps<{ question: QuestionListItem }>()

const { t } = useAppI18n()
const store = useQuestionsStore()

const editing = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

/** Which status change is in flight, so only that button shows its progress. */
const acting = ref<'approve' | 'reject' | null>(null)
const actionError = ref<string | null>(null)

const sourceOpen = ref(false)
const detail = ref<QuestionDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref<string | null>(null)

async function toggleSource(): Promise<void> {
  sourceOpen.value = !sourceOpen.value
  if (!sourceOpen.value || detail.value !== null || detailLoading.value) {
    return
  }
  detailLoading.value = true
  detailError.value = null
  try {
    detail.value = await getQuestion(props.question.id)
  } catch (error) {
    detailError.value = translateApiError(error)
  } finally {
    detailLoading.value = false
  }
}

function startEditing(): void {
  saveError.value = null
  editing.value = true
}

function cancelEditing(): void {
  editing.value = false
  saveError.value = null
}

async function onSave(payload: QuestionPayload): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    await store.updatePayload(props.question.id, payload)
    editing.value = false
    // The stored payload changed, so the cached source panel is the only part
    // still holding the old response; drop it and refetch when asked again.
    detail.value = null
  } catch (error) {
    saveError.value = translateApiError(error)
  } finally {
    saving.value = false
  }
}

async function onApprove(): Promise<void> {
  acting.value = 'approve'
  actionError.value = null
  try {
    await store.approve(props.question.id)
  } catch (error) {
    actionError.value = translateApiError(error)
  } finally {
    acting.value = null
  }
}

async function onReject(): Promise<void> {
  acting.value = 'reject'
  actionError.value = null
  try {
    await store.reject(props.question.id)
  } catch (error) {
    actionError.value = translateApiError(error)
  } finally {
    acting.value = null
  }
}
</script>

<template>
  <QuestionCard :question="question">
    <template #actions>
      <AppButton variant="secondary" @click="toggleSource">
        {{ sourceOpen ? t('review.source.hide') : t('review.source.show') }}
      </AppButton>
      <AppButton
        v-if="!editing"
        variant="secondary"
        :disabled="acting !== null"
        @click="startEditing"
      >
        {{ t('editor.edit') }}
      </AppButton>
      <AppButton :disabled="acting !== null || editing" @click="onApprove">
        {{ acting === 'approve' ? t('review.approving') : t('review.approve') }}
      </AppButton>
      <AppButton variant="secondary" :disabled="acting !== null || editing" @click="onReject">
        {{ acting === 'reject' ? t('review.rejecting') : t('review.reject') }}
      </AppButton>
    </template>

    <QuestionEditor
      v-if="editing"
      :question="question"
      :saving="saving"
      :error-message="saveError"
      @save="onSave"
      @cancel="cancelEditing"
    />
    <QuestionDisplay v-else :question="question" />

    <template #footer>
      <p v-if="actionError !== null" class="form-error">{{ actionError }}</p>

      <section v-if="sourceOpen" class="review-source">
        <h4 class="review-source__title">{{ t('review.source.title') }}</h4>
        <p v-if="detailLoading" class="form-hint">{{ t('review.source.loading') }}</p>
        <p v-else-if="detailError !== null" class="form-error">{{ detailError }}</p>
        <template v-else-if="detail !== null">
          <p v-if="detail.source_chunks.length === 0" class="form-hint">
            {{ t('review.source.empty') }}
          </p>
          <article
            v-for="chunk in detail.source_chunks"
            :key="chunk.id"
            class="review-source__chunk"
          >
            <p class="review-source__chunk-id">
              {{ t('review.source.chunk', { id: chunk.id }) }}
            </p>
            <MarkdownContent :source="chunk.content" />
          </article>
        </template>
      </section>
    </template>
  </QuestionCard>
</template>

<style scoped>
.review-source {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background-soft);
}

.review-source__title {
  font-size: 0.9375rem;
}

.review-source__chunk {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--color-border);
}

.review-source__chunk:first-of-type {
  padding-top: 0;
  border-top: none;
}

.review-source__chunk-id {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
}
</style>
