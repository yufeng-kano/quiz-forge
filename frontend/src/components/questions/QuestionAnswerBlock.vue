<script setup lang="ts">
/**
 * The answer / explanation block of a rendered question.
 *
 * docs/frontend.md requires the answer to be visually distinct from the stem;
 * doing that here once keeps all six type renderers consistent. A left rule is
 * the whole distinction — `variant` only changes its colour, the answer itself
 * (accent) against the supporting explanation (neutral)
 * (docs/frontend.md 設計節制原則 — 分割線優先於面板).
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
  gap: var(--space-1);
  padding-left: var(--space-3);
  border-left: 3px solid transparent;
}

.answer-block--answer {
  border-left-color: var(--color-accent);
}

.answer-block--explanation {
  border-left-color: var(--color-border-hover);
}

.answer-block__label {
  color: var(--color-heading);
  font-weight: 600;
}

.answer-block__body {
  color: var(--color-text);
  overflow-wrap: anywhere;
}
</style>
