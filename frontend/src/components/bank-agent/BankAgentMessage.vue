<script setup lang="ts">
import { computed } from 'vue'

import { CONVERSATION_ROLE_ASSISTANT, type ConversationMessage } from '@/api'
import MarkdownContent from '@/components/MarkdownContent.vue'
import BankAgentProposals from '@/components/bank-agent/BankAgentProposals.vue'
import BankAgentSteps from '@/components/bank-agent/BankAgentSteps.vue'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'

/**
 * One conversation message.
 *
 * A user message is just its text. An assistant message additionally carries
 * what it proposed and how it got there: the proposal rows
 * (`proposed_question_ids`) and the expandable 查詢過程 log (`steps`), both
 * defined by docs/decisions/2026-08-17-bank-agent-semantic-selection.md D5/D6.
 *
 * Body text goes through `MarkdownContent` (same sanitizer as document pages)
 * so lists, emphasis and code in the assistant reply render.
 */
const props = defineProps<{ message: ConversationMessage }>()

const emit = defineEmits<{ openProposal: [questionId: number] }>()

const { t } = useAppI18n()

const isAssistant = computed(() => props.message.role === CONVERSATION_ROLE_ASSISTANT)

const meta = computed(() =>
  t('bankAgent.messages.meta', {
    role: isAssistant.value ? t('bankAgent.messages.assistant') : t('bankAgent.messages.user'),
    datetime: formatDateTime(props.message.created_at),
  }),
)
</script>

<template>
  <article class="message" :class="isAssistant ? 'message--assistant' : 'message--user'">
    <p class="message__meta">{{ meta }}</p>
    <MarkdownContent class="message__content" :source="message.content" />

    <BankAgentProposals
      v-if="isAssistant && message.proposed_question_ids.length > 0"
      :question-ids="message.proposed_question_ids"
      @open="emit('openProposal', $event)"
    />

    <BankAgentSteps v-if="isAssistant" :steps="message.steps" />
  </article>
</template>

<style scoped>
.message {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0;
}

/* Speakers tell themselves apart with a muted meta line; the user's text
   sits on a light tint rather than inside a bordered card
   (docs/decisions/2026-08-17-bank-on-questions-page.md D12). */
.message--user .message__content {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-accent-soft);
}

/* Readable secondary line, not shrunken grey filler: it is the only thing that
   says who is speaking (docs/decisions/2026-08-17-ui-design-restraint.md D20) */
.message__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.message__content {
  font-size: var(--font-size-md);
  line-height: 1.7;
}
</style>
