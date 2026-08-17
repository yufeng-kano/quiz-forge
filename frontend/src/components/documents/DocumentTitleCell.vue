<script setup lang="ts">
import { computed } from 'vue'

import type { DocumentListItem } from '@/api'
import { displayUrl } from '@/utils/url'

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

// URL imports carry the address as their title; show the decoded, readable
// form in both the cell and the tooltip (src/utils/url.ts).
const displayTitle = computed(() => displayUrl(props.document.title))

const tooltip = computed(() => {
  const url = props.document.source_url
  return url === null ? displayTitle.value : `${displayTitle.value}\n${displayUrl(url)}`
})
</script>

<template>
  <span class="document-title text-ellipsis" :title="tooltip">{{ displayTitle }}</span>
</template>

<style scoped>
.document-title {
  min-width: 0;
  width: 100%;
  color: var(--color-heading);
  font-weight: 600;
}
</style>
