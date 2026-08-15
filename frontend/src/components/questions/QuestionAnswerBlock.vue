<script setup lang="ts">
/**
 * The answer / explanation block of a rendered question.
 *
 * docs/frontend.md requires the answer to be visually distinct from the stem;
 * doing that here once keeps all six type renderers consistent. `variant`
 * separates the answer itself (accent tint) from the supporting explanation
 * (neutral tint).
 */
withDefaults(defineProps<{ label: string; variant?: 'answer' | 'explanation' }>(), {
  variant: 'answer',
})
</script>

<template>
  <div class="answer-block" :class="`answer-block--${variant}`">
    <p class="answer-block__label">{{ label }}</p>
    <div class="answer-block__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.answer-block {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.6rem 0.85rem;
  border-left: 3px solid transparent;
  border-radius: 0 6px 6px 0;
}

.answer-block--answer {
  border-left-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.answer-block--explanation {
  border-left-color: var(--color-border-hover);
  background: var(--color-background-soft);
}

.answer-block__label {
  color: var(--color-heading);
  font-size: 0.8125rem;
  font-weight: 600;
}

.answer-block__body {
  color: var(--color-text);
  overflow-wrap: anywhere;
}
</style>
