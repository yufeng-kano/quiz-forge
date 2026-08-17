<script setup lang="ts">
import { computed } from 'vue'

import type { DocumentPage } from '@/api'
import AppButton from '@/components/AppButton.vue'
import MarkdownContent from '@/components/MarkdownContent.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'

/**
 * One parsed page: its status, the retry control for a failed page (a retry is
 * always per page, never per document, per the .rule UX rules) and the parsed
 * Markdown.
 *
 * The reading column is one surface: a page is a block separated by a hairline,
 * not a bordered card (docs/decisions/2026-08-17-ui-design-restraint.md D16 /
 * D22). Retry is icon-only, its wording in `aria-label` and tooltip (D18).
 *
 * A failed retry is reported by the view as a toast, so the block carries no
 * error state of its own.
 */
const props = defineProps<{
  page: DocumentPage
  retrying: boolean
}>()

const emit = defineEmits<{ retry: [pageId: number] }>()

const { t } = useAppI18n()

const canRetry = computed(() => props.page.status === 'failed')

const markdown = computed(() => props.page.markdown ?? '')

const retryLabel = computed(() =>
  props.retrying
    ? t('documentDetail.pages.retrying')
    : t('documentDetail.pages.retryAria', { no: props.page.page_no }),
)
</script>

<template>
  <article class="page-block">
    <header class="page-block__head">
      <h3 class="page-block__title">
        {{ t('documentDetail.pages.pageNo', { no: page.page_no }) }}
      </h3>
      <StatusBadge :status="page.status" />
      <AppButton
        v-if="canRetry"
        class="page-block__retry"
        variant="ghost"
        icon
        size="sm"
        :disabled="retrying"
        :aria-label="retryLabel"
        :title="retryLabel"
        @click="emit('retry', page.id)"
      >
        <AppIcon name="refresh" :size="16" />
      </AppButton>
    </header>

    <MarkdownContent v-if="markdown.trim() !== ''" :source="markdown" />
    <p v-else class="page-block__empty">{{ t('documentDetail.pages.noContent') }}</p>
  </article>
</template>

<style scoped>
.page-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.page-block__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.page-block__title {
  font-size: var(--font-size-base);
}

.page-block__retry {
  margin-left: auto;
}

.page-block__empty {
  color: var(--color-text-muted);
}
</style>
