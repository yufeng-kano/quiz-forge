<script setup lang="ts">
import { ref, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import ProgressText from '@/components/ProgressText.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useQuestionsStore } from '@/stores/questions'
import { useToastsStore } from '@/stores/toasts'

/**
 * 「有 N 題尚未向量化」 plus the 補向量 action
 * (docs/question-bank.md 題目向量化與語意搜尋).
 *
 * The count is the list envelope's own `unembedded_total`, so it describes the
 * questions the current filters match — not the whole table — and disappears
 * on its own once every one of them has an embedding.
 *
 * Embedding is a background job (`embed_questions`), never inline work: the
 * button creates it, this block shows its progress, and the bank is reloaded
 * when it is done so the count reflects what actually got embedded. A single
 * question failing is recorded in the job's own error and does not stop the
 * rest (docs/question-bank.md — 單題失敗記入 jobs.error 不中斷其他題), which is
 * why a `done` job with an error still shows it.
 */
const { t } = useAppI18n()
const store = useQuestionsStore()
const toasts = useToastsStore()

const starting = ref(false)

const { status, progress, error, requestError, isActive } = useJobPolling(() => store.embedJobId)

async function onEmbed(): Promise<void> {
  starting.value = true
  try {
    const jobId = await store.startEmbedBacklog()
    toasts.success(t('bank.embed.started', { id: jobId }))
  } catch (requestFailure) {
    toasts.error(translateApiError(requestFailure))
  } finally {
    starting.value = false
  }
}

watch(status, (value, previous) => {
  if (value === previous || store.embedJobId === null) {
    return
  }
  // Read the job's error before dropping the id: clearing it unsubscribes the
  // polling, and with it the `error` this message is built from.
  const jobError = error.value
  if (value === 'done') {
    store.clearEmbedJob()
    toasts.push(
      jobError === null ? 'success' : 'error',
      jobError === null ? t('bank.embed.done') : t('bank.embed.partial', { error: jobError }),
    )
    // Newly embedded questions change both the unembedded count and what a
    // semantic search can reach, so the current page is refetched.
    void store.loadBank({ silent: true })
    return
  }
  if (value === 'failed') {
    store.clearEmbedJob()
    toasts.error(
      jobError === null
        ? t('bank.embed.failedNoDetail')
        : t('bank.embed.failed', { error: jobError }),
    )
  }
})
</script>

<template>
  <div v-if="store.bankUnembeddedTotal > 0 || isActive" class="embed-notice">
    <span class="embed-notice__text">
      {{ t('bank.embed.notice', { count: store.bankUnembeddedTotal }) }}
    </span>

    <template v-if="isActive">
      <StatusBadge v-if="status !== null" :status="status" />
      <span class="embed-notice__running">{{ t('bank.embed.running') }}</span>
      <ProgressText :progress="progress" />
    </template>

    <AppButton v-else variant="secondary" size="sm" :disabled="starting" @click="onEmbed">
      {{ starting ? t('bank.embed.starting') : t('bank.embed.action') }}
    </AppButton>

    <span v-if="requestError !== null" class="embed-notice__error">{{ requestError }}</span>
  </div>
</template>

<style scoped>
/* A one-line notice above the list: neutral rather than an error tone, since
   nothing is broken — those questions simply have not been embedded yet */
.embed-notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-2) 0;
}

.embed-notice__text {
  color: var(--color-status-pending-text);
  font-size: var(--font-size-md);
}

.embed-notice__running {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.embed-notice__error {
  color: var(--color-status-failed-text);
  font-size: var(--font-size-md);
}
</style>
