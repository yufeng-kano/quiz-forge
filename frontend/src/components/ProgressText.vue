<script setup lang="ts">
import { computed } from 'vue'
import { useAppI18n } from '@/i18n'

/**
 * Displays a job's textual progress.
 *
 * `jobs.progress` is free-form text (docs/architecture.md); the common shape is
 * `12/40`. A recognised ratio is rendered with a percentage, anything else is
 * shown verbatim rather than forced into a format it does not have.
 */
const props = defineProps<{ progress: string | null }>()

const { t } = useAppI18n()

const RATIO_PATTERN = /^(\d+)\s*\/\s*(\d+)$/

const text = computed(() => {
  const raw = props.progress?.trim() ?? ''
  if (raw === '') {
    return t('job.progress.notStarted')
  }
  const match = RATIO_PATTERN.exec(raw)
  if (match === null) {
    return raw
  }
  const [, currentText, totalText] = match
  if (currentText === undefined || totalText === undefined) {
    return raw
  }
  const current = Number(currentText)
  const total = Number(totalText)
  if (total <= 0) {
    return raw
  }
  return t('job.progress.ratio', {
    current,
    total,
    percent: Math.round((current / total) * 100),
  })
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
