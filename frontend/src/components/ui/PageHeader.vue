<script setup lang="ts">
/**
 * Header bar of a page: compact title on the left, the page's primary actions
 * on the right.
 *
 * Every view renders exactly one of these as its first element, so the shell
 * has the same anchor line on every route. It sticks to the top of the content
 * region, which is what keeps the main action reachable while a long table or
 * a long document is scrolled.
 *
 * A count belongs in the title itself when it is the page's main number
 * (「題庫 - 共 7 題」). `subtitle` is only for secondary data — a document id,
 * a file count — never a how-to sentence about what the page is for.
 */
defineProps<{
  /** Localised page title, optionally already including a count. */
  title: string
  /** Secondary data under the title: a count, a document id. Not a how-to sentence. */
  subtitle?: string
}>()
</script>

<template>
  <header class="page-header-bar">
    <div class="page-header-bar__titles">
      <h1 class="page-header-bar__title text-ellipsis" :title="title">{{ title }}</h1>
      <p v-if="subtitle !== undefined" class="page-header-bar__subtitle">{{ subtitle }}</p>
      <div v-if="$slots.meta" class="page-header-bar__meta">
        <slot name="meta" />
      </div>
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
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3) var(--space-5);
  min-height: var(--page-header-height);
  margin: 0 calc(-1 * var(--content-padding-x));
  padding: var(--space-4) var(--content-padding-x);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
}

.page-header-bar__titles {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

/* A page title can be a document's own title, which on a URL import is whatever
   the page was called — one line with a tooltip, never a wrapped block */
.page-header-bar__title {
  max-width: 100%;
  font-size: var(--font-size-xl);
}

.page-header-bar__subtitle {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  max-width: var(--reading-max-width);
}

.page-header-bar__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  margin-top: var(--space-1);
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.page-header-bar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}
</style>
