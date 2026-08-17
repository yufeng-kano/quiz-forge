<script setup lang="ts">
import { EXPORT_HEADER_FIELD_NAMES, type ExportHeaderField, type ExportHeaderFields } from '@/api'
import { EXPORT_HEADER_FIELD_LABEL_KEYS } from '@/export/labels'
import { useAppI18n } from '@/i18n'

/**
 * 表頭欄位 — which columns the paper's student-information row carries
 * (docs/export.md 卷面結構).
 *
 * Four fixed checkboxes, all ticked by default, so the group stays one compact
 * line and never grows: the set is defined by the API
 * (`EXPORT_HEADER_FIELD_NAMES`), not by any data. Unticking all four omits the
 * row entirely — the empty group shows that by itself, so the field carries a
 * label and the boxes and nothing else (docs/frontend.md 設計節制原則).
 */
const fields = defineModel<ExportHeaderFields>({ required: true })

const { t } = useAppI18n()

function onToggle(field: ExportHeaderField, event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) {
    return
  }
  const next: ExportHeaderFields = { ...fields.value }
  next[field] = target.checked
  fields.value = next
}
</script>

<template>
  <div class="form-field">
    <span class="form-label">{{ t('exports.headerFields.label') }}</span>

    <div class="header-fields">
      <label v-for="field in EXPORT_HEADER_FIELD_NAMES" :key="field" class="header-fields__item">
        <input type="checkbox" :checked="fields[field]" @change="onToggle(field, $event)" />
        <span>{{ t(EXPORT_HEADER_FIELD_LABEL_KEYS[field]) }}</span>
      </label>
    </div>
  </div>
</template>

<style scoped>
.header-fields {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}

.header-fields__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  white-space: nowrap;
}
</style>
