<script setup lang="ts">
import { onMounted, watch } from 'vue'

import BankAgentProposalCard from '@/components/bank-agent/BankAgentProposalCard.vue'
import { useAppI18n } from '@/i18n'
import { useBankAgentStore } from '@/stores/bankAgent'

/**
 * The questions one assistant message proposed, as a bounded, self-scrolling
 * list of flat rows (docs/frontend.md 清單有界原則;
 * docs/decisions/2026-08-17-bank-on-questions-page.md D12).
 *
 * A click on a row is forwarded as `open` so the bank page can show that
 * question on the left. This list never writes the export selection
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D14).
 */
const props = defineProps<{ questionIds: readonly number[] }>()

const emit = defineEmits<{ open: [questionId: number] }>()

const { t } = useAppI18n()
const store = useBankAgentStore()

/** Resolve the rows behind the ids; already-known ids cost no request. */
function resolve(): void {
  void store.ensureProposedQuestions(props.questionIds)
}

onMounted(resolve)
watch(() => props.questionIds, resolve)
</script>

<template>
  <section class="proposals">
    <h4 class="proposals__title">
      {{ t('bankAgent.proposals.title', { count: questionIds.length }) }}
    </h4>

    <p v-if="store.proposedQuestionsError !== null" class="form-error">
      {{ store.proposedQuestionsError }}
    </p>

    <ul class="proposals__list">
      <li v-for="questionId in questionIds" :key="questionId">
        <BankAgentProposalCard :question-id="questionId" @open="emit('open', $event)" />
      </li>
    </ul>
  </section>
</template>

<style scoped>
/* Spacing, not a panel, separates the proposals from the reply above them
   (docs/decisions/2026-08-17-ui-design-restraint.md D22) */
.proposals {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-2);
}

/* The count is the one thing the bounded scroll box hides, so it is kept —
   at a readable size rather than shrunken grey (D20) */
.proposals__title {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-weight: 600;
}

/* A proposal can be a whole paper's worth of questions; the block keeps its
   own height and scrolls inside instead of stretching the conversation */
.proposals__list {
  display: flex;
  flex-direction: column;
  max-height: 15rem;
  overflow-y: auto;
  padding: 0;
  list-style: none;
}

.proposals__list > li {
  border-bottom: 1px solid var(--color-hairline);
}

.proposals__list > li:last-child {
  border-bottom: none;
}
</style>
