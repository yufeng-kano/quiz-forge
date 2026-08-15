<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { getUsage, type UsageSummary } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import UsageTable from '@/components/usage/UsageTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { modelRows, purposeRows } from '@/usage/rows'

/**
 * 用量 — the running total of what the LLM calls have cost in tokens
 * (.rule 使用者體驗規則: 提供使用者查看累計用量).
 *
 * Everything on the page comes from one `GET /api/v1/usage` response: the four
 * grand totals, plus the same numbers broken down by model and by purpose.
 * There is nothing to poll — usage only changes when a job runs — so the page
 * loads once and offers a refresh button.
 */
const { t } = useAppI18n()

const summary = ref<UsageSummary | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)
const loaded = ref(false)

const byModel = computed(() => (summary.value === null ? [] : modelRows(summary.value)))
const byPurpose = computed(() => (summary.value === null ? [] : purposeRows(summary.value)))

/** No `llm_usage` rows at all: both groupings come back empty. */
const isEmpty = computed(
  () => loaded.value && byModel.value.length === 0 && byPurpose.value.length === 0,
)

const totals = computed(() => {
  const current = summary.value
  if (current === null) {
    return []
  }
  return [
    { key: 'callCount', label: t('usage.metric.callCount'), value: current.total.call_count },
    {
      key: 'promptTokens',
      label: t('usage.metric.promptTokens'),
      value: current.total.prompt_tokens,
    },
    {
      key: 'completionTokens',
      label: t('usage.metric.completionTokens'),
      value: current.total.completion_tokens,
    },
    { key: 'totalTokens', label: t('usage.metric.totalTokens'), value: current.total.total_tokens },
  ]
})

async function load(): Promise<void> {
  loading.value = true
  try {
    summary.value = await getUsage()
    loaded.value = true
    loadError.value = null
  } catch (error) {
    loadError.value = translateApiError(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <PageHeader :title="t('pages.usage.title')" :subtitle="t('pages.usage.description')" />

    <div class="usage__actions">
      <AppButton variant="secondary" :disabled="loading" @click="load">
        {{ t('usage.refresh') }}
      </AppButton>
      <span v-if="loading" class="form-hint">{{ t('usage.loading') }}</span>
    </div>

    <p v-if="loadError !== null" class="usage__error">{{ loadError }}</p>

    <template v-if="summary !== null && !isEmpty">
      <section class="usage__section">
        <h3 class="usage__title">{{ t('usage.totals.title') }}</h3>
        <ul class="usage__totals">
          <li v-for="metric in totals" :key="metric.key" class="usage__metric">
            <span class="usage__metric-label">{{ metric.label }}</span>
            <span class="usage__metric-value">{{ formatCount(metric.value) }}</span>
          </li>
        </ul>
      </section>

      <section class="usage__section">
        <h3 class="usage__title">{{ t('usage.byModel.title') }}</h3>
        <UsageTable :column-label="t('usage.byModel.column')" :rows="byModel" />
      </section>

      <section class="usage__section">
        <h3 class="usage__title">{{ t('usage.byPurpose.title') }}</h3>
        <UsageTable :column-label="t('usage.byPurpose.column')" :rows="byPurpose" />
      </section>
    </template>

    <EmptyState
      v-else-if="isEmpty"
      :title="t('usage.emptyTitle')"
      :description="t('usage.emptyDescription')"
    />
  </div>
</template>

<style scoped>
.usage__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.usage__section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.usage__title {
  font-size: 1rem;
}

.usage__totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.75rem;
  padding: 0;
  list-style: none;
}

.usage__metric {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

.usage__metric-label {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.usage__metric-value {
  color: var(--color-heading);
  font-size: 1.25rem;
  font-variant-numeric: tabular-nums;
}

.usage__error {
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-status-failed-border);
  border-radius: 8px;
  background: var(--color-status-failed-bg);
  color: var(--color-status-failed-text);
  overflow-wrap: anywhere;
}
</style>
