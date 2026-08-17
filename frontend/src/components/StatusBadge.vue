<script setup lang="ts">
import { computed } from 'vue'
import { useAppI18n, type MessageKey } from '@/i18n'

/**
 * Status as coloured text, shared by the status vocabularies the backend uses:
 * jobs (`pending` / `running` / `done` / `failed`), documents / pages
 * (`pending` / `processing` / `ready` / `failed`) and questions (`draft` /
 * `approved` / `rejected`, docs/question-bank.md 狀態機).
 *
 * Colour is the only decoration — no pill, chip, or filled capsule. Both
 * vocabularies are plain string columns with no CHECK constraint, so the prop
 * is a string: a value outside the table below is shown verbatim in a neutral
 * tone instead of disappearing or crashing the page.
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
  draft: { tone: 'pending', labelKey: 'status.draft' },
  approved: { tone: 'done', labelKey: 'status.approved' },
  rejected: { tone: 'failed', labelKey: 'status.rejected' },
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
  white-space: nowrap;
}

.status-badge--pending {
  color: var(--color-status-pending-text);
}

.status-badge--running {
  color: var(--color-status-running-text);
}

.status-badge--done {
  color: var(--color-status-done-text);
}

.status-badge--failed {
  color: var(--color-status-failed-text);
}

.status-badge--unknown {
  color: var(--color-status-unknown-text);
}
</style>
