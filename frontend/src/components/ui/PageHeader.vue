<script setup lang="ts">
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'

/**
 * Header bar of a page: the page name and its count on the left, its primary
 * actions on the right.
 *
 * The name is visible again (docs/decisions/2026-08-17-professional-form-pages.md
 * D25): on a page without a full-height table or stat cards it is the one
 * anchor the layout has, so hiding it made the sparse form pages read as
 * unfinished. What D23 still forbids stays forbidden: no purpose sentence, no
 * tutorial line.
 *
 * `heading` replaces the page name when the title is data rather than a route —
 * the document's own title on 文件詳情.
 *
 * Every view renders exactly one of these as its first element, so the shell
 * has the same anchor line on every route. It sticks to the top of the content
 * region, which is what keeps the main action reachable while a long table or
 * a long document is scrolled.
 */
defineProps<{
  /** Localised page name, the visible `<h1>` of the page. */
  pageName: string
  /** Replaces the page name when the page's title is data (文件詳情). */
  heading?: string
  /** Localised aria-label; renders the back icon button on the left. */
  backLabel?: string
}>()

const emit = defineEmits<{ back: [] }>()
</script>

<template>
  <header class="page-header-bar">
    <AppButton
      v-if="backLabel !== undefined"
      variant="secondary"
      icon
      :aria-label="backLabel"
      :title="backLabel"
      @click="emit('back')"
    >
      <AppIcon name="chevronLeft" :size="16" />
    </AppButton>

    <h1 class="page-header-bar__title text-ellipsis" :title="heading">
      {{ heading ?? pageName }}
    </h1>

    <div v-if="$slots.meta" class="page-header-bar__meta">
      <slot name="meta" />
    </div>

    <div v-if="$slots.actions" class="page-header-bar__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header-bar {
  position: sticky;
  top: 0;
  z-index: var(--z-page-header);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  /* An icon button (2.25rem) plus this padding stays under the token height, so
     every page gets a bar of exactly `--page-header-height`; only 文件詳情,
     whose heading can wrap controls in, may grow past it. */
  min-height: var(--page-header-height);
  margin: 0 calc(-1 * var(--content-padding-x));
  padding: var(--space-2) var(--content-padding-x);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
}

/* A visible heading may be a document's own title, which on a URL import is
   whatever the page was called — one line with a tooltip, never a wrapped
   block. */
.page-header-bar__title {
  min-width: 0;
  max-width: 100%;
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.page-header-bar__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  min-width: 0;
  color: var(--color-text-muted);
}

.page-header-bar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}
</style>
