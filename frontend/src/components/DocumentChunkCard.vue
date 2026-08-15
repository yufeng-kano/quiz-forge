<script setup lang="ts">
import { computed, ref } from 'vue'

import type { DocumentChunk } from '@/api'
import { useAppI18n } from '@/i18n'

/**
 * One chunk: its category path, its tags and a collapsible view of the text
 * that was classified and embedded.
 */
const props = defineProps<{
  chunk: DocumentChunk
  /** 1-based position of the chunk within the document. */
  index: number
  /** Category names from the outermost known ancestor down to the chunk's own. */
  categoryPath: readonly string[]
}>()

const { t } = useAppI18n()

const categoryLabel = computed(() =>
  props.categoryPath.length === 0
    ? t('documentDetail.chunks.uncategorized')
    : props.categoryPath.join(t('documentDetail.chunks.categorySeparator')),
)

const embeddingLabel = computed(() =>
  props.chunk.has_embedding
    ? t('documentDetail.chunks.embedded')
    : t('documentDetail.chunks.notEmbedded'),
)

const expanded = ref(false)

/** `<details>` owns the open state; mirror it so the summary label can follow. */
function onToggle(event: Event): void {
  const details = event.target
  if (details instanceof HTMLDetailsElement) {
    expanded.value = details.open
  }
}
</script>

<template>
  <article class="chunk-card">
    <header class="chunk-card__head">
      <span class="chunk-card__index">
        {{ t('documentDetail.chunks.chunkNo', { no: index }) }}
      </span>
      <span class="chunk-card__category" :class="{ 'is-muted': categoryPath.length === 0 }">
        {{ categoryLabel }}
      </span>
      <span class="chunk-card__embedding">{{ embeddingLabel }}</span>
    </header>

    <ul v-if="chunk.tags.length > 0" class="chunk-card__tags">
      <li v-for="(tag, tagIndex) in chunk.tags" :key="`${tagIndex}-${tag}`" class="chunk-card__tag">
        {{ tag }}
      </li>
    </ul>

    <details class="chunk-card__details" @toggle="onToggle">
      <summary class="chunk-card__summary">
        {{ expanded ? t('documentDetail.chunks.collapse') : t('documentDetail.chunks.expand') }}
      </summary>
      <p class="chunk-card__content">{{ chunk.content }}</p>
    </details>
  </article>
</template>

<style scoped>
.chunk-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.9rem 1.1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background);
}

.chunk-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem 0.9rem;
}

.chunk-card__index {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
}

.chunk-card__category {
  color: var(--color-heading);
  font-weight: 600;
}

.chunk-card__category.is-muted {
  color: var(--color-text-muted);
  font-weight: normal;
}

.chunk-card__embedding {
  margin-left: auto;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

.chunk-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  list-style: none;
  padding: 0;
}

.chunk-card__tag {
  padding: 0.05rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-background-soft);
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

.chunk-card__summary {
  color: var(--color-accent);
  cursor: pointer;
  font-size: 0.875rem;
  width: fit-content;
}

.chunk-card__content {
  margin-top: 0.5rem;
  padding: 0.75rem 0.9rem;
  border-radius: 6px;
  background: var(--color-background-soft);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
