<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary'
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  { variant: 'primary', type: 'button', disabled: false },
)
</script>

<template>
  <button class="app-button" :class="`app-button--${variant}`" :type="type" :disabled="disabled">
    <slot />
  </button>
</template>

<style scoped>
.app-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.4rem 0.9rem;
  border: 1px solid transparent;
  border-radius: 6px;
  font: inherit;
  line-height: 1.4;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.app-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.app-button--primary {
  color: #ffffff;
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.app-button--primary:hover:not(:disabled) {
  background: var(--color-accent-strong);
  border-color: var(--color-accent-strong);
}

.app-button--secondary {
  color: var(--color-heading);
  background: var(--color-background);
  border-color: var(--color-border);
}

.app-button--secondary:hover:not(:disabled) {
  background: var(--color-background-soft);
  border-color: var(--color-border-hover);
}
</style>
