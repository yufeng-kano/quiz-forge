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
import { useToastsStore } from '@/stores/toasts'

/**
 * One draft question in the review queue: render it, compare it against the
 * source text it was generated from, edit it, then adopt or discard it
 * (docs/question-bank.md 審題流程).
 *
 * Adopting and discarding both go through the store, which puts the *server's*
 * version of the row back into the lists — so the card only leaves the queue
 * once the status change is confirmed, never on optimism alone. Their outcome
 * is a toast, because the card itself disappears with the change and could not
 * show a message of its own; an edit stays on screen and keeps its 422 next to
 * the fields it is about.
 *
 * The checkbox feeds the page's batch selection; the source text comes from
 * `GET /api/v1/questions/{id}` and is fetched the first time it is asked for,
 * not for every card in the list.
 *
 * The queue is a list of questions divided by hairlines, not a stack of
 * floating bordered cards, and the source text is quoted with a left rule
 * instead of a second frame inside the first
 * (docs/frontend.md 設計節制原則 — 卡片不是骨架、禁止卡中卡). Every row here
 * is a `draft`, so the card only shows a status when one is not.
 */
const props = defineProps<{ question: QuestionListItem; selected: boolean; busy: boolean }>()

const emit = defineEmits<{ toggleSelect: [] }>()

const { t } = useAppI18n()
const store = useQuestionsStore()
const toasts = useToastsStore()

const editing = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

/** Which status change is in flight, so only that button shows its progress. */
const acting = ref<'approve' | 'reject' | null>(null)

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
    toasts.success(t('review.saved', { id: props.question.id }))
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
  try {
    await store.approve(props.question.id)
    toasts.success(t('review.approved', { id: props.question.id }))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    acting.value = null
  }
}

async function onReject(): Promise<void> {
  acting.value = 'reject'
  try {
    await store.reject(props.question.id)
    toasts.success(t('review.rejected', { id: props.question.id }))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    acting.value = null
  }
}
</script>

<template>
  <QuestionCard :question="question" expected-status="draft">
    <template #select>
      <input
        type="checkbox"
        class="review-card__checkbox"
        :checked="props.selected"
        :disabled="props.busy"
        :aria-label="t('review.batch.checkbox', { id: question.id })"
        @change="emit('toggleSelect')"
      />
    </template>

    <template #actions>
      <AppButton variant="secondary" size="sm" @click="toggleSource">
        {{ sourceOpen ? t('review.source.hide') : t('review.source.show') }}
      </AppButton>
      <AppButton
        v-if="!editing"
        variant="secondary"
        size="sm"
        :disabled="acting !== null || props.busy"
        @click="startEditing"
      >
        {{ t('editor.edit') }}
      </AppButton>
      <AppButton size="sm" :disabled="acting !== null || editing || props.busy" @click="onApprove">
        {{ acting === 'approve' ? t('review.approving') : t('review.approve') }}
      </AppButton>
      <AppButton
        variant="secondary"
        size="sm"
        :disabled="acting !== null || editing || props.busy"
        @click="onReject"
      >
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
      <section v-if="sourceOpen" class="review-source">
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
            <MarkdownContent :source="chunk.content" />
          </article>
        </template>
      </section>
    </template>
  </QuestionCard>
</template>

<style scoped>
.review-card__checkbox {
  width: 1.05rem;
  height: 1.05rem;
  cursor: pointer;
}

/* Quoted source material: a left rule marks it as not-the-question, which is
   all the distinction it needs inside the row. */
.review-source {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-left: var(--space-3);
  border-left: 2px solid var(--color-border);
}

.review-source__chunk {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-hairline);
}

.review-source__chunk:first-of-type {
  padding-top: 0;
  border-top: none;
}
</style>
