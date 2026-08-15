<script setup lang="ts">
import { computed } from 'vue'

import { answersDocxUrl, questionsDocxUrl, type ExportListItem } from '@/api'
import { useAppI18n } from '@/i18n'
import { formatDateTime } from '@/i18n/datetime'
import { paperSizeLabel } from '@/export/labels'

/**
 * One past export with its two download links.
 *
 * The links are plain anchors to the same-origin docx endpoints, which respond
 * with `Content-Disposition: attachment` and the paper's filename — no fetch,
 * no blob, no filename invented on the client. A file the job has not written
 * yet (`*_available === false`) renders as disabled text instead of a link that
 * could only 404.
 */
const props = defineProps<{ item: ExportListItem }>()

const { t } = useAppI18n()

const meta = computed(() =>
  t('exports.history.meta', {
    id: props.item.id,
    paper: paperSizeLabel(props.item.paper_size),
    count: props.item.question_count,
    datetime: formatDateTime(props.item.created_at),
  }),
)

const hasMissingFile = computed(
  () => !props.item.questions_available || !props.item.answers_available,
)
</script>

<template>
  <article class="export-row">
    <p class="export-row__meta">{{ meta }}</p>

    <div class="export-row__downloads">
      <a
        v-if="item.questions_available"
        class="export-row__link"
        :href="questionsDocxUrl(item.id)"
        >{{ t('exports.history.questions') }}</a
      >
      <span v-else class="export-row__link export-row__link--disabled" aria-disabled="true">
        {{ t('exports.history.questions') }}
      </span>

      <a v-if="item.answers_available" class="export-row__link" :href="answersDocxUrl(item.id)">{{
        t('exports.history.answers')
      }}</a>
      <span v-else class="export-row__link export-row__link--disabled" aria-disabled="true">
        {{ t('exports.history.answers') }}
      </span>
    </div>

    <p v-if="hasMissingFile" class="form-hint">{{ t('exports.history.unavailable') }}</p>
  </article>
</template>

<style scoped>
.export-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

.export-row__meta {
  color: var(--color-heading);
  font-variant-numeric: tabular-nums;
}

.export-row__downloads {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.25rem;
}

.export-row__link {
  color: var(--color-accent);
}

.export-row__link--disabled {
  color: var(--color-text-muted);
  cursor: not-allowed;
  text-decoration: line-through;
}
</style>
