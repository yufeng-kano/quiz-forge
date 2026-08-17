<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { getUsage, type UsageSummary } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
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
 * grand totals as `StatCard`s, plus the same numbers broken down by model and
 * by purpose as two sortable tables, each its own bounded scroll region. There
 * is nothing to poll — usage only changes when a job runs — so the page loads
 * once and offers a refresh button, whose failure is a toast rather than a
 * silent no-op.
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

/** First load only; a refresh keeps the numbers on screen instead of blanking them. */
const totalsLoading = computed(() => loading.value && total.value === null)

/** The four grand totals, headline number first. */
const totals = computed(() => [
  {
    key: 'total_tokens',
    label: t('usage.metric.totalTokens'),
    value: total.value?.total_tokens,
  },
  {
    key: 'prompt_tokens',
    label: t('usage.metric.promptTokens'),
    value: total.value?.prompt_tokens,
  },
  {
    key: 'completion_tokens',
    label: t('usage.metric.completionTokens'),
    value: total.value?.completion_tokens,
  },
  {
    key: 'call_count',
    label: t('usage.metric.callCount'),
    value: total.value?.call_count,
  },
])

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
    <PageHeader :page-name="t('nav.usage')">
      <template #actions>
        <AppButton
          variant="secondary"
          icon
          :disabled="loading"
          :aria-label="t('usage.refresh')"
          :title="t('usage.refresh')"
          @click="load"
        >
          <AppIcon name="refresh" :size="16" />
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="loadError !== null" class="error-banner">{{ loadError }}</p>

    <section class="usage__totals">
      <StatCard
        v-for="metric in totals"
        :key="metric.key"
        :label="metric.label"
        :value="formatCount(metric.value ?? 0)"
        :loading="totalsLoading"
      />
    </section>

    <p v-if="isEmpty" class="usage__empty">{{ t('usage.emptyTitle') }}</p>

    <template v-else>
      <!-- The tables carry no heading of their own: the first column already
           names what each one groups by (docs/frontend.md 設計節制原則 D19).
           The name stays as the region's accessible name. -->
      <section class="usage__section" :aria-label="t('usage.byModel.title')">
        <DataTable
          :columns="modelColumns"
          :rows="byModel"
          :row-key="(row: UsageTableRow) => row.key"
          :loading="loading && byModel.length === 0"
          :empty-title="t('usage.emptyTitle')"
        >
          <template #label="{ row }">
            <span class="usage__row-label text-ellipsis" :title="row.label">{{ row.label }}</span>
          </template>
        </DataTable>
      </section>

      <section class="usage__section" :aria-label="t('usage.byPurpose.title')">
        <DataTable
          :columns="purposeColumns"
          :rows="byPurpose"
          :row-key="(row: UsageTableRow) => row.key"
          :loading="loading && byPurpose.length === 0"
          :empty-title="t('usage.emptyTitle')"
        >
          <template #label="{ row }">
            <span class="usage__row-label text-ellipsis" :title="row.label">{{ row.label }}</span>
          </template>
        </DataTable>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* The four totals are one self-contained dataset, so they keep their card
   borders while the rest of the app has none — the documented exception to
   「卡片不是版面骨架」(docs/frontend.md 視覺風格, D24). */
.usage__totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-3);
}

.usage__empty {
  padding: var(--space-6) 0;
  color: var(--color-text-muted);
  text-align: center;
}

/* A model name (`openrouter/…`) and an unknown purpose string are open-ended:
   one line with the full text in the tooltip, never a pill and never wrapped
   (docs/frontend.md 清單有界原則, D17). */
.usage__row-label {
  color: var(--color-heading);
  font-weight: 600;
}

/* Two independent datasets, so each table bounds its own height and owns its
   own scrollbar instead of pushing the other off screen (D21). */
.usage__section {
  --data-table-max-height: max(18rem, calc(50vh - 6rem));
}
</style>
