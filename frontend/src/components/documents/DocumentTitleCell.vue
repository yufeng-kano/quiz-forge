<script setup lang="ts">
import type { DocumentListItem } from '@/api'

/**
 * A document's title with, for a URL import, the page it came from.
 *
 * Both lines cut the same way: one line with the full text in the tooltip
 * (docs/frontend.md 清單有界原則), never a wrapped block that makes a row six
 * lines tall. Width comes from the table cell (`min-width: 0` +
 * `table-layout: fixed`); this cell does not cap itself.
 */
const props = defineProps<{ document: DocumentListItem }>()
</script>

<template>
  <div class="document-title">
    <span class="document-title__text text-ellipsis" :title="props.document.title">
      {{ props.document.title }}
    </span>
    <a
      v-if="props.document.source_url !== null"
      class="document-title__source text-ellipsis"
      :href="props.document.source_url"
      :title="props.document.source_url"
      target="_blank"
      rel="noopener noreferrer"
      @click.stop
    >
      {{ props.document.source_url }}
    </a>
  </div>
</template>

<style scoped>
.document-title {
  min-width: 0;
  width: 100%;
}

.document-title__text {
  color: var(--color-heading);
  font-weight: 600;
}

.document-title__source {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}
</style>
