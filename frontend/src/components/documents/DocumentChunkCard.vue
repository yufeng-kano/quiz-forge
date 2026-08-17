<script setup lang="ts">
import { computed, ref } from 'vue'

import type { DocumentChunk } from '@/api'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'

/**
 * One chunk: its category path, its tags and a collapsible view of the text
 * that was classified and embedded.
 *
 * A block on the same reading surface as the pages above it — hairline instead
 * of a card, plain text instead of tag pills, and no panel around the expanded
 * text (docs/decisions/2026-08-17-ui-design-restraint.md D16 / D17 / D22).
 * The header row is the `<summary>`, so the chevron alone carries the
 * expand/collapse affordance (D18) and 已建立向量 — the normal state repeated on
 * every chunk — is not written out at all (D20); only its absence is.
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

const tagsLabel = computed(() => props.chunk.tags.join(t('documentDetail.chunks.tagSeparator')))

const expanded = ref(false)

const toggleLabel = computed(() =>
  expanded.value ? t('documentDetail.chunks.collapse') : t('documentDetail.chunks.expand'),
)

/** `<details>` owns the open state; mirror it so the chevron can follow. */
function onToggle(event: Event): void {
  const details = event.target
  if (details instanceof HTMLDetailsElement) {
    expanded.value = details.open
  }
}
</script>

<template>
  <details class="chunk-block" @toggle="onToggle">
    <summary class="chunk-block__head" :title="toggleLabel">
      <span class="chunk-block__index">
        {{ t('documentDetail.chunks.chunkNo', { no: index }) }}
      </span>
      <span class="chunk-block__category" :class="{ 'is-muted': categoryPath.length === 0 }">
        {{ categoryLabel }}
      </span>
      <span v-if="!chunk.has_embedding" class="chunk-block__embedding">
        {{ t('documentDetail.chunks.notEmbedded') }}
      </span>
      <AppIcon
        class="chunk-block__chevron"
        :name="expanded ? 'chevronUp' : 'chevronDown'"
        :size="16"
      />
      <span v-if="chunk.tags.length > 0" class="chunk-block__tags">{{ tagsLabel }}</span>
    </summary>

    <p class="chunk-block__content">{{ chunk.content }}</p>
  </details>
</template>

<style scoped>
.chunk-block {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.chunk-block__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1) var(--space-3);
  list-style: none;
  cursor: pointer;
}

.chunk-block__head::-webkit-details-marker {
  display: none;
}

.chunk-block__index {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.chunk-block__category {
  min-width: 0;
  color: var(--color-heading);
  font-weight: 600;
  overflow-wrap: anywhere;
}

.chunk-block__category.is-muted {
  color: var(--color-text-muted);
  font-weight: normal;
}

/* Only the missing embedding is worth a word: it is why a chunk stays out of
   semantic search. The normal state is silent. */
.chunk-block__embedding {
  color: var(--color-status-pending-text);
}

.chunk-block__chevron {
  margin-left: auto;
  color: var(--color-text-muted);
}

/* Tags are open content: plain text on its own row, never pills */
.chunk-block__tags {
  width: 100%;
  color: var(--color-text-muted);
  overflow-wrap: anywhere;
}

.chunk-block__content {
  margin-top: var(--space-2);
  max-width: var(--reading-max-width);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
