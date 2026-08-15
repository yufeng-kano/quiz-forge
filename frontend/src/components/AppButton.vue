<script setup lang="ts">
/**
 * The only button style in the app.
 *
 * `primary` carries the one main action of a page or dialog, `secondary` every
 * other control, `ghost` a control that sits inside a dense surface (a table
 * row, a card header) where a bordered button would be noise, and `danger` a
 * destructive confirmation. `sm` is the size for table rows and card headers.
 */
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md'
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  { variant: 'primary', size: 'md', type: 'button', disabled: false },
)
</script>

<template>
  <button
    class="app-button"
    :class="[`app-button--${variant}`, `app-button--${size}`]"
    :type="type"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<style scoped>
.app-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font: inherit;
  line-height: 1.4;
  white-space: nowrap;
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

.app-button--md {
  padding: 0.4rem 0.9rem;
}

.app-button--sm {
  padding: 0.2rem 0.6rem;
  font-size: var(--font-size-md);
}

.app-button--primary {
  color: var(--color-on-accent);
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

.app-button--ghost {
  color: var(--color-text-muted);
  background: none;
}

.app-button--ghost:hover:not(:disabled) {
  background: var(--color-background-mute);
  color: var(--color-heading);
}

.app-button--danger {
  color: var(--color-on-accent);
  background: var(--color-danger);
  border-color: var(--color-danger);
}

.app-button--danger:hover:not(:disabled) {
  background: var(--color-danger-strong);
  border-color: var(--color-danger-strong);
}
</style>
