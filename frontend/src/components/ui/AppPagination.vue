<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import AppIcon from './AppIcon.vue'

/**
 * Page controls for a server-paginated list.
 *
 * It owns no state: the current page and the total come from whichever store
 * issued the query, and pressing a control asks for a page rather than moving
 * anything itself. Every list that pages through a `{ items, total, limit,
 * offset }` envelope uses this one control, so paging looks the same
 * everywhere.
 */
const props = defineProps<{
  /** 1-based page currently on screen. */
  page: number
  pageCount: number
  /** Row count of the whole result, not of the page. */
  total: number
  /** Blocks the controls while a page is being fetched. */
  disabled?: boolean
}>()

const emit = defineEmits<{ change: [page: number] }>()

const { t } = useAppI18n()

const canGoBack = computed(() => props.page > 1 && !(props.disabled ?? false))
const canGoForward = computed(() => props.page < props.pageCount && !(props.disabled ?? false))

function go(page: number): void {
  if (page !== props.page && page >= 1 && page <= props.pageCount) {
    emit('change', page)
  }
}
</script>

<template>
  <nav class="pagination" :aria-label="t('pagination.label')">
    <span class="pagination__summary">
      {{
        t('pagination.summary', {
          page: formatCount(props.page),
          pageCount: formatCount(props.pageCount),
          total: formatCount(props.total),
        })
      }}
    </span>

    <div class="pagination__controls">
      <AppButton
        variant="secondary"
        size="sm"
        :disabled="!canGoBack"
        :aria-label="t('pagination.previous')"
        @click="go(props.page - 1)"
      >
        <AppIcon name="chevronLeft" :size="16" />
        {{ t('pagination.previous') }}
      </AppButton>
      <AppButton
        variant="secondary"
        size="sm"
        :disabled="!canGoForward"
        :aria-label="t('pagination.next')"
        @click="go(props.page + 1)"
      >
        {{ t('pagination.next') }}
        <AppIcon name="chevronRight" :size="16" />
      </AppButton>
    </div>
  </nav>
</template>

<style scoped>
.pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-4);
}

.pagination__summary {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.pagination__controls {
  display: flex;
  gap: var(--space-2);
}
</style>
