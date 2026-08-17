<script setup lang="ts">
import { computed, ref } from 'vue'

import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useBankAgentStore } from '@/stores/bankAgent'
import { useToastsStore } from '@/stores/toasts'

/**
 * Where a turn is written and sent.
 *
 * Sending stores the message and queues the turn's job; the reply arrives when
 * that job finishes, so the box is disabled while one is running rather than
 * letting a second turn be queued behind the first. Already-selected export
 * ids still travel with the request as context; the box does not narrate that.
 *
 * Enter sends, Shift+Enter is a newline. There is no submit button
 * (docs/frontend.md 選題助手空狀態／輸入框).
 */
const { t } = useAppI18n()
const store = useBankAgentStore()
const toasts = useToastsStore()

const text = ref('')

const hasConversation = computed(() => store.activeId !== null)

const canSend = computed(() => hasConversation.value && !store.isBusy && text.value.trim() !== '')

async function onSend(): Promise<void> {
  if (!canSend.value) {
    return
  }
  const content = text.value.trim()
  try {
    await store.send(content)
    text.value = ''
  } catch (error) {
    toasts.error(translateApiError(error))
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
    return
  }
  event.preventDefault()
  void onSend()
}
</script>

<template>
  <div class="composer">
    <label class="form-field">
      <span class="sr-only">{{ t('bankAgent.composer.label') }}</span>
      <textarea
        v-model="text"
        class="form-textarea composer__input"
        rows="3"
        :placeholder="t('bankAgent.composer.placeholder')"
        :disabled="!hasConversation || store.isBusy"
        @keydown="onKeydown"
      />
    </label>
  </div>
</template>

<style scoped>
.composer {
  display: flex;
  flex-direction: column;
}

.composer__input {
  height: 4.75rem;
  resize: none;
  overflow-y: auto;
  font-size: var(--font-size-md);
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
