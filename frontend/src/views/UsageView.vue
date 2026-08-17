<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { getUsage, type UsageSummary } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import DataTable from '@/components/ui/DataTable.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatCard from '@/components/ui/StatCard.vue'
import type { DataTableColumn } from '@/components/ui/dataTable'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { formatCount } from '@/i18n/number'
import { useToastsStore } from '@/stores/toasts'
import { modelRows, purposeRows, type UsageTableRow } from '@/usage/rows'

/**
 * 用量 — the running total of what the LLM calls have cost in tokens
 * (.rule 使用者體驗規則: 提供使用者查看累計用量).
 *
 * Everything on the page comes from one `GET /api/v1/usage` response: the four
 * grand totals as cards, plus the same numbers broken down by model and by
 * purpose as two sortable tables. There is nothing to poll — usage only
 * changes when a job runs — so the page loads once and offers a refresh
 * button, whose failure is a toast rather than a silent no-op.
 */
const { t } = useAppI18n()
const toasts = useToastsStore()

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

const total = computed(() => summary.value?.total ?? null)

/**
 * The breakdown tables carry the same four numbers and differ only in what
 * their first column names, so one column set is built for both. Sorting on
 * every column is what makes 「哪個模型吃掉最多 token」 answerable without
 * reading every row; the rows arrive heaviest-first already.
 */
function breakdownColumns(firstColumnLabel: string): DataTableColumn<UsageTableRow>[] {
  return [
    {
      key: 'label',
      label: firstColumnLabel,
      value: (row) => row.label,
      sortValue: (row) => row.label,
    },
    {
      key: 'call_count',
      label: t('usage.metric.callCount'),
      value: (row) => formatCount(row.call_count),
      sortValue: (row) => row.call_count,
      align: 'end',
      nowrap: true,
      width: '8rem',
    },
    {
      key: 'prompt_tokens',
      label: t('usage.metric.promptTokens'),
      value: (row) => formatCount(row.prompt_tokens),
      sortValue: (row) => row.prompt_tokens,
      align: 'end',
      nowrap: true,
      width: '9rem',
    },
    {
      key: 'completion_tokens',
      label: t('usage.metric.completionTokens'),
      value: (row) => formatCount(row.completion_tokens),
      sortValue: (row) => row.completion_tokens,
      align: 'end',
      nowrap: true,
      width: '9rem',
    },
    {
      key: 'total_tokens',
      label: t('usage.metric.totalTokens'),
      value: (row) => formatCount(row.total_tokens),
      sortValue: (row) => row.total_tokens,
      align: 'end',
      nowrap: true,
      width: '9rem',
    },
  ]
}

const modelColumns = computed(() => breakdownColumns(t('usage.byModel.column')))
const purposeColumns = computed(() => breakdownColumns(t('usage.byPurpose.column')))

async function load(): Promise<void> {
  loading.value = true
  try {
    summary.value = await getUsage()
    loaded.value = true
    loadError.value = null
  } catch (error) {
    const message = translateApiError(error)
    loadError.value = message
    toasts.error(message)
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
    <PageHeader :title="t('pages.usage.title')">
      <template #actions>
        <AppButton variant="secondary" :disabled="loading" @click="load">
          {{ t('usage.refresh') }}
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="loadError !== null" class="error-banner">
      {{ loadError }}
      <AppButton variant="secondary" :disabled="loading" @click="load">
        {{ t('usage.refresh') }}
      </AppButton>
    </p>

    <section class="usage__cards">
      <StatCard
        :label="t('usage.metric.totalTokens')"
        :value="formatCount(total?.total_tokens ?? 0)"
        :hint="t('usage.totals.hint')"
        :loading="loading && total === null"
      />
      <StatCard
        :label="t('usage.metric.promptTokens')"
        :value="formatCount(total?.prompt_tokens ?? 0)"
        :loading="loading && total === null"
      />
      <StatCard
        :label="t('usage.metric.completionTokens')"
        :value="formatCount(total?.completion_tokens ?? 0)"
        :loading="loading && total === null"
      />
      <StatCard
        :label="t('usage.metric.callCount')"
        :value="formatCount(total?.call_count ?? 0)"
        :loading="loading && total === null"
      />
    </section>

    <EmptyState
      v-if="isEmpty"
      :title="t('usage.emptyTitle')"
      :description="t('usage.emptyDescription')"
    />

    <template v-else>
      <section class="usage__section">
        <h2 class="card-title">{{ t('usage.byModel.title') }}</h2>
        <DataTable
          :columns="modelColumns"
          :rows="byModel"
          :row-key="(row: UsageTableRow) => row.key"
          :loading="loading && byModel.length === 0"
          :empty-title="t('usage.emptyTitle')"
        />
      </section>

      <section class="usage__section">
        <h2 class="card-title">{{ t('usage.byPurpose.title') }}</h2>
        <DataTable
          :columns="purposeColumns"
          :rows="byPurpose"
          :row-key="(row: UsageTableRow) => row.key"
          :loading="loading && byPurpose.length === 0"
          :empty-title="t('usage.emptyTitle')"
        />
      </section>
    </template>
  </div>
</template>

<style scoped>
.usage__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-3);
}

.usage__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  /* Two tables share the page, so neither takes the full viewport height */
  --data-table-max-height: max(18rem, calc(100vh - 28rem));
}
</style>
