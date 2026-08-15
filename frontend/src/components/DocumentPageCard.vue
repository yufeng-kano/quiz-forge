<script setup lang="ts">
import { computed } from 'vue'

import type { DocumentPage } from '@/api'
import AppButton from '@/components/AppButton.vue'
import MarkdownContent from '@/components/MarkdownContent.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppI18n } from '@/i18n'

/**
 * One parsed page: its status, the retry control for a failed page (a retry is
 * always per page, never per document, per the .rule UX rules) and the parsed
 * Markdown.
 */
const props = defineProps<{
  page: DocumentPage
  retrying: boolean
  error: string | null
}>()

const emit = defineEmits<{ retry: [pageId: number] }>()

const { t } = useAppI18n()

const canRetry = computed(() => props.page.status === 'failed')

const markdown = computed(() => props.page.markdown ?? '')
</script>

<template>
  <article class="page-card">
    <header class="page-card__head">
      <h4 class="page-card__title">{{ t('documentDetail.pages.pageNo', { no: page.page_no }) }}</h4>
      <StatusBadge :status="page.status" />
      <AppButton
        v-if="canRetry"
        class="page-card__retry"
        variant="secondary"
        :disabled="retrying"
        @click="emit('retry', page.id)"
      >
        {{ retrying ? t('documentDetail.pages.retrying') : t('documentDetail.pages.retry') }}
      </AppButton>
    </header>

    <p v-if="error !== null" class="page-card__error">{{ error }}</p>

    <MarkdownContent v-if="markdown.trim() !== ''" :source="markdown" />
    <p v-else class="page-card__empty">{{ t('documentDetail.pages.noContent') }}</p>
  </article>
</template>

<style scoped>
.page-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1rem 1.2rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

.page-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.page-card__title {
  color: var(--color-heading);
  font-size: 0.9375rem;
  font-weight: 600;
}

.page-card__retry {
  margin-left: auto;
}

.page-card__error {
  color: var(--color-status-failed-text);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}

.page-card__empty {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}
</style>
