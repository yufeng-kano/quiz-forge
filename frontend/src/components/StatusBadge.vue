<script setup lang="ts">
import { computed } from 'vue'
import { useAppI18n, type MessageKey } from '@/i18n'

/**
 * Status pill, shared by the two status vocabularies the backend uses:
 * jobs (`pending` / `running` / `done` / `failed`) and documents / pages
 * (`pending` / `processing` / `ready` / `failed`).
 *
 * Both are plain string columns with no CHECK constraint, so the prop is a
 * string: a value outside the table below is shown verbatim in a neutral tone
 * instead of disappearing or crashing the page.
 */
const props = defineProps<{ status: string }>()

const { t } = useAppI18n()

type StatusTone = 'pending' | 'running' | 'done' | 'failed' | 'unknown'

interface StatusPresentation {
  tone: StatusTone
  labelKey: MessageKey
}

const STATUS_PRESENTATIONS: Record<string, StatusPresentation> = {
  pending: { tone: 'pending', labelKey: 'status.pending' },
  running: { tone: 'running', labelKey: 'status.running' },
  processing: { tone: 'running', labelKey: 'status.processing' },
  done: { tone: 'done', labelKey: 'status.done' },
  ready: { tone: 'done', labelKey: 'status.ready' },
  failed: { tone: 'failed', labelKey: 'status.failed' },
}

const presentation = computed<StatusPresentation | null>(
  () => STATUS_PRESENTATIONS[props.status] ?? null,
)

const tone = computed<StatusTone>(() => presentation.value?.tone ?? 'unknown')

const label = computed(() => {
  const known = presentation.value
  return known === null ? props.status : t(known.labelKey)
})
</script>

<template>
  <span class="status-badge" :class="`status-badge--${tone}`">{{ label }}</span>
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

.status-badge--unknown {
  color: var(--color-status-unknown-text);
  background: var(--color-status-unknown-bg);
  border-color: var(--color-status-unknown-border);
}
</style>
