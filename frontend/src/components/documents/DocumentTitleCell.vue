<script setup lang="ts">
import { computed } from 'vue'

import type { DocumentListItem } from '@/api'

/**
 * A document's title in the library table: one line, cut with an ellipsis, the
 * full title and — for a URL import — the page it came from in the tooltip
 * (docs/decisions/2026-08-17-documents-workspace-layout.md L3, docs/frontend.md
 * 清單有界原則). The source URL is not a second visible line: the 來源 column
 * already says where the document came from, and the address itself is on the
 * detail page. Width comes from the table cell (`table-layout: fixed`); this
 * cell does not cap itself.
 */
const props = defineProps<{ document: DocumentListItem }>()

const tooltip = computed(() => {
  const url = props.document.source_url
  return url === null ? props.document.title : `${props.document.title}\n${url}`
})
</script>

<template>
  <span class="document-title text-ellipsis" :title="tooltip">{{ props.document.title }}</span>
</template>

<style scoped>
.document-title {
  min-width: 0;
  width: 100%;
  color: var(--color-heading);
  font-weight: 600;
}
</style>
