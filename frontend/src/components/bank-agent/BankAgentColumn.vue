<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type { Conversation } from '@/api'
import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import BankAgentComposer from '@/components/bank-agent/BankAgentComposer.vue'
import BankAgentMessage from '@/components/bank-agent/BankAgentMessage.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useBankAgentStore } from '@/stores/bankAgent'
import { useToastsStore } from '@/stores/toasts'

/**
 * Expanded 選題助手 column on 題庫: conversation switcher, transcript, and
 * composer. Polling lives on the bank page so it keeps running while this
 * column is collapsed (docs/decisions/2026-08-17-bank-on-questions-page.md D10).
 */
defineProps<{
  turnProgress: string | null
  turnError: string | null
  turnRequestError: string | null
}>()

const emit = defineEmits<{
  collapse: []
  retryTurn: []
  openProposal: [questionId: number]
}>()

const { t } = useAppI18n()
const store = useBankAgentStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

const creating = ref(false)
const deleting = ref(false)
const messageList = ref<HTMLElement | null>(null)

function titleOf(conversation: Conversation): string {
  return conversation.title === '' ? t('bankAgent.conversations.untitled') : conversation.title
}

const pickerValue = computed(() => (store.activeId === null ? '' : String(store.activeId)))

function onPick(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLSelectElement) || target.value === '') {
    return
  }
  void store.selectConversation(Number(target.value))
}

async function onCreate(): Promise<void> {
  creating.value = true
  try {
    const conversation = await store.create()
    await store.selectConversation(conversation.id)
    toasts.success(t('bank.agent.created'))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    creating.value = false
  }
}

async function onDelete(): Promise<void> {
  const conversation = store.activeConversation
  if (conversation === null) {
    return
  }
  const confirmed = await confirm({
    title: t('bankAgent.conversations.deleteTitle'),
    message: t('bankAgent.conversations.deleteMessage', { title: titleOf(conversation) }),
    confirmLabel: t('bankAgent.conversations.deleteConfirm'),
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }
  deleting.value = true
  try {
    await store.remove(conversation.id)
    toasts.success(t('bankAgent.conversations.deleted'))
    const next = store.conversations[0]
    if (next !== undefined) {
      await store.selectConversation(next.id)
    }
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    deleting.value = false
  }
}

watch(
  () => store.messages.length,
  async () => {
    await nextTick()
    const element = messageList.value
    if (element !== null) {
      element.scrollTop = element.scrollHeight
    }
  },
)
</script>

<template>
  <aside class="agent">
    <header class="agent__header">
      <h2 class="agent__title">{{ t('bank.agent.title') }}</h2>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :aria-label="t('bank.agent.close')"
        :title="t('bank.agent.close')"
        @click="emit('collapse')"
      >
        <AppIcon name="chevronRight" :size="16" />
      </AppButton>
    </header>

    <div class="agent__switcher">
      <label class="agent__picker">
        <span class="sr-only">{{ t('bank.agent.picker') }}</span>
        <select
          class="form-select"
          :value="pickerValue"
          :disabled="store.conversationsLoading"
          @change="onPick"
        >
          <option v-if="store.conversations.length === 0" value="">
            {{ t('bank.agent.pickerEmpty') }}
          </option>
          <option
            v-for="conversation in store.conversations"
            :key="conversation.id"
            :value="String(conversation.id)"
          >
            {{ titleOf(conversation) }}
          </option>
        </select>
      </label>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :disabled="creating"
        :aria-label="t('bank.agent.new')"
        :title="t('bank.agent.new')"
        @click="onCreate"
      >
        <AppIcon name="plus" :size="16" />
      </AppButton>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :disabled="deleting || store.activeId === null"
        :aria-label="t('bankAgent.conversations.delete')"
        :title="t('bankAgent.conversations.delete')"
        @click="onDelete"
      >
        <AppIcon name="trash" :size="16" />
      </AppButton>
    </div>

    <p v-if="store.conversationsError !== null" class="error-banner">
      {{ store.conversationsError }}
      <AppButton
        variant="secondary"
        icon
        size="sm"
        :aria-label="t('bankAgent.reload')"
        :title="t('bankAgent.reload')"
        @click="store.loadConversations()"
      >
        <AppIcon name="refresh" :size="16" />
      </AppButton>
    </p>

    <p v-if="store.messagesError !== null" class="error-banner">
      {{ store.messagesError }}
      <AppButton
        variant="secondary"
        icon
        size="sm"
        :aria-label="t('bankAgent.reload')"
        :title="t('bankAgent.reload')"
        @click="store.loadMessages()"
      >
        <AppIcon name="refresh" :size="16" />
      </AppButton>
    </p>

    <div ref="messageList" class="agent__messages">
      <template v-if="store.messagesLoading && store.messages.length === 0">
        <AppSkeleton width="60%" />
        <AppSkeleton />
        <AppSkeleton width="80%" />
      </template>

      <ul v-else-if="store.messages.length > 0" class="agent__message-list">
        <li v-for="message in store.messages" :key="message.id">
          <BankAgentMessage :message="message" @open-proposal="emit('openProposal', $event)" />
        </li>
      </ul>

      <p v-else class="agent__empty">{{ t('bankAgent.messages.emptyTitle') }}</p>

      <!--
        Turn state belongs to the conversation timeline: running progress and
        failed+retry render at the bottom of the message list and scroll with
        it, so the footer keeps holding only the composer
        (docs/decisions/2026-08-18-bank-agent-progress-in-conversation.md H1).
      -->
      <div v-if="store.isActiveTurnPending" class="agent__turn">
        <span class="agent__turn-label">{{ t('bankAgent.turn.running') }}</span>
        <ProgressText :progress="turnProgress" />
      </div>

      <div v-else-if="store.hasActiveTurnFailed" class="agent__turn-failed">
        <p class="form-error">
          {{
            turnError === null
              ? t('bankAgent.turn.failedNoDetail')
              : t('bankAgent.turn.failed', { error: turnError })
          }}
        </p>
        <div>
          <AppButton size="sm" variant="secondary" @click="emit('retryTurn')">
            {{ t('bankAgent.turn.retry') }}
          </AppButton>
        </div>
      </div>
    </div>

    <div class="agent__footer">
      <p v-if="turnRequestError !== null" class="form-error">{{ turnRequestError }}</p>

      <BankAgentComposer />
    </div>
  </aside>
</template>

<style scoped>
.agent {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.agent__header {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3) var(--space-2);
}

.agent__title {
  font-size: var(--font-size-md);
}

.agent__switcher {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-3) var(--space-2);
}

.agent__picker {
  flex: 1;
  min-width: 0;
}

.agent .error-banner {
  margin: 0 var(--space-3) var(--space-2);
}

.agent__messages {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--space-3);
}

.agent__empty {
  margin: auto;
  color: var(--color-text-faint);
  font-size: var(--font-size-md);
  text-align: center;
}

.agent__message-list {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 0;
  list-style: none;
}

/* The footer IS the input surface (H2): no padding, so the borderless
   composer spans the full column width; the top hairline is the only
   separator from the conversation area. */
.agent__footer {
  display: flex;
  flex: none;
  flex-direction: column;
  gap: var(--space-2);
  padding: 0;
  border-top: 1px solid var(--color-hairline);
}

/* The rare send-request error sits above the input surface; keep it off the
   column edges (H2). */
.agent__footer > .form-error {
  margin: 0;
  padding: var(--space-2) var(--space-3) 0;
}

.agent__turn {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0 var(--space-3);
}

.agent__turn-label {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.agent__turn-failed {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) 0 var(--space-3);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
