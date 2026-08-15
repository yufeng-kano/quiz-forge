<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

/**
 * Renders parsed page Markdown.
 *
 * `v-html` is safe here because `renderMarkdown()` escapes raw HTML while
 * parsing and sanitizes the result with DOMPurify; see `@/utils/markdown`.
 */
const props = defineProps<{ source: string }>()

const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <div class="markdown" v-html="html" />
</template>

<style scoped>
.markdown {
  color: var(--color-text);
  overflow-wrap: anywhere;
}

.markdown :deep(> *) {
  margin-bottom: 0.85rem;
}

.markdown :deep(> *:last-child) {
  margin-bottom: 0;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4),
.markdown :deep(h5),
.markdown :deep(h6) {
  margin-top: 1.4rem;
  color: var(--color-heading);
  font-weight: 600;
  line-height: 1.35;
}

.markdown :deep(h1) {
  font-size: 1.25rem;
}

.markdown :deep(h2) {
  font-size: 1.125rem;
}

.markdown :deep(h3),
.markdown :deep(h4),
.markdown :deep(h5),
.markdown :deep(h6) {
  font-size: 1rem;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  padding-left: 1.5rem;
}

.markdown :deep(li) {
  margin-bottom: 0.25rem;
}

.markdown :deep(blockquote) {
  padding: 0.25rem 0 0.25rem 0.9rem;
  border-left: 3px solid var(--color-border);
  color: var(--color-text-muted);
}

.markdown :deep(img) {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0.5rem 0;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background-soft);
}

.markdown :deep(code) {
  padding: 0.05rem 0.3rem;
  border-radius: 4px;
  background: var(--color-background-mute);
  font-size: 0.9em;
}

.markdown :deep(pre) {
  overflow-x: auto;
  padding: 0.75rem 0.9rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background-soft);
}

.markdown :deep(pre code) {
  padding: 0;
  background: none;
}

/* Wide tables scroll inside their own container instead of stretching the page */
.markdown :deep(.markdown-scroll) {
  overflow-x: auto;
}

.markdown :deep(table) {
  border-collapse: collapse;
  min-width: 100%;
}

.markdown :deep(th),
.markdown :deep(td) {
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--color-border);
  text-align: left;
  vertical-align: top;
}

.markdown :deep(th) {
  background: var(--color-background-soft);
  color: var(--color-heading);
  font-weight: 600;
}

.markdown :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border);
}
</style>
