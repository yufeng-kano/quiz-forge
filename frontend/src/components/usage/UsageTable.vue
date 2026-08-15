<script setup lang="ts">
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import type { UsageTableRow } from '@/usage/rows'

/**
 * One usage grouping as a table. Both groupings carry the same four numbers,
 * so only the first column's heading differs and the caller passes it in.
 */
defineProps<{ columnLabel: string; rows: readonly UsageTableRow[] }>()

const { t } = useAppI18n()
</script>

<template>
  <div class="usage-table">
    <table>
      <thead>
        <tr>
          <th scope="col">{{ columnLabel }}</th>
          <th scope="col" class="usage-table__number">{{ t('usage.metric.callCount') }}</th>
          <th scope="col" class="usage-table__number">{{ t('usage.metric.promptTokens') }}</th>
          <th scope="col" class="usage-table__number">{{ t('usage.metric.completionTokens') }}</th>
          <th scope="col" class="usage-table__number">{{ t('usage.metric.totalTokens') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key">
          <th scope="row" class="usage-table__label">{{ row.label }}</th>
          <td class="usage-table__number">{{ formatCount(row.call_count) }}</td>
          <td class="usage-table__number">{{ formatCount(row.prompt_tokens) }}</td>
          <td class="usage-table__number">{{ formatCount(row.completion_tokens) }}</td>
          <td class="usage-table__number">{{ formatCount(row.total_tokens) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.usage-table {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 0.5rem 0.9rem;
  text-align: left;
  white-space: nowrap;
}

thead th {
  color: var(--color-heading);
  font-size: 0.875rem;
  font-weight: 600;
  background: var(--color-background-soft);
  border-bottom: 1px solid var(--color-border);
}

tbody tr + tr th,
tbody tr + tr td {
  border-top: 1px solid var(--color-border);
}

.usage-table__label {
  color: var(--color-heading);
  font-weight: 600;
  overflow-wrap: anywhere;
  white-space: normal;
}

.usage-table__number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
