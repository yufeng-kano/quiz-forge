<script setup lang="ts">
import { computed } from 'vue'
import { useAppI18n } from '@/i18n'

import type { JobStatus } from '@/api'

const props = defineProps<{ status: JobStatus }>()

const { t } = useAppI18n()

const label = computed(() => t(`job.status.${props.status}`))
</script>

<template>
  <span class="status-badge" :class="`status-badge--${props.status}`">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.55rem;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 0.8125rem;
  line-height: 1.5;
  white-space: nowrap;
}

.status-badge--pending {
  color: var(--color-status-pending-text);
  background: var(--color-status-pending-bg);
  border-color: var(--color-status-pending-border);
}

.status-badge--running {
  color: var(--color-status-running-text);
  background: var(--color-status-running-bg);
  border-color: var(--color-status-running-border);
}

.status-badge--done {
  color: var(--color-status-done-text);
  background: var(--color-status-done-bg);
  border-color: var(--color-status-done-border);
}

.status-badge--failed {
  color: var(--color-status-failed-text);
  background: var(--color-status-failed-bg);
  border-color: var(--color-status-failed-border);
}
</style>
