<script setup lang="ts">
/**
 * Loading placeholder.
 *
 * `line` stands in for a line of text (inherits the surrounding line height),
 * `block` for a card or a chart area whose height the caller states.
 */
withDefaults(
  defineProps<{
    variant?: 'line' | 'block'
    /** Any CSS length; a fraction of the container reads as an uneven text run. */
    width?: string
    /** Only meaningful for `block`; `line` takes its height from the text size. */
    height?: string
  }>(),
  { variant: 'line', width: '100%', height: '4rem' },
)
</script>

<template>
  <span
    class="skeleton"
    :class="`skeleton--${variant}`"
    :style="{ width, height: variant === 'block' ? height : undefined }"
    aria-hidden="true"
  />
</template>

<style scoped>
.skeleton {
  display: block;
  border-radius: var(--radius-sm);
  background: linear-gradient(
    90deg,
    var(--color-background-mute) 0%,
    var(--color-background-soft) 50%,
    var(--color-background-mute) 100%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.4s ease-in-out infinite;
}

.skeleton--line {
  height: 0.75em;
  margin: 0.25em 0;
}

.skeleton--block {
  border-radius: var(--radius-md);
}

@keyframes skeleton-shimmer {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -200% 0;
  }
}

/* A shimmering placeholder is decoration, not information */
@media (prefers-reduced-motion: reduce) {
  .skeleton {
    animation: none;
  }
}
</style>
