<script setup lang="ts">
import { computed } from 'vue'
import { useAppI18n, type MessageKey } from '@/i18n'

/**
 * Displays a job's textual progress.
 *
 * `jobs.progress` is free-form text (docs/architecture.md). The ingestion
 * pipeline writes a ratio plus the unit it counts — `3/12 pages` while parsing
 * pages, `chunks 3/10` while classifying — so a recognised unit is translated
 * and rendered with a percentage. Anything the pattern does not cover is shown
 * verbatim rather than being reshaped into a format it does not have.
 */
const props = defineProps<{ progress: string | null }>()

const { t } = useAppI18n()

/** `12/40`, with the counted unit optionally in front of or behind the ratio. */
const PROGRESS_PATTERN = /^(?:([A-Za-z]+)\s+)?(\d+)\s*\/\s*(\d+)(?:\s+([A-Za-z]+))?$/

/** Units `backend.ingestion.pipeline` reports. */
const UNIT_LABEL_KEYS: Record<string, MessageKey> = {
  pages: 'job.progress.unit.pages',
  chunks: 'job.progress.unit.chunks',
}

const text = computed(() => {
  const raw = props.progress?.trim() ?? ''
  if (raw === '') {
    return t('job.progress.notStarted')
  }
  const match = PROGRESS_PATTERN.exec(raw)
  if (match === null) {
    return raw
  }
  const [, prefixUnit, currentText, totalText, suffixUnit] = match
  if (currentText === undefined || totalText === undefined) {
    return raw
  }
  const current = Number(currentText)
  const total = Number(totalText)
  if (total <= 0) {
    return raw
  }
  const percent = Math.round((current / total) * 100)
  const unitToken = prefixUnit ?? suffixUnit
  if (unitToken === undefined) {
    return t('job.progress.ratio', { current, total, percent })
  }
  const unitKey = UNIT_LABEL_KEYS[unitToken.toLowerCase()]
  if (unitKey === undefined) {
    // An unknown unit would be dropped by the translated form; keep the
    // backend's own wording instead of losing what is being counted.
    return raw
  }
  return t('job.progress.ratioWithUnit', { current, total, percent, unit: t(unitKey) })
})
</script>

<template>
  <span class="progress-text">{{ text }}</span>
</template>

<style scoped>
.progress-text {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
