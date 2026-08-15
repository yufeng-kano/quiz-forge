<script setup lang="ts">
/** Empty-state block. The caller resolves the wording from the locale file and
 * passes it in, so this component contains no text of its own. */
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <div class="empty-state">
    <p class="empty-state__title">{{ title }}</p>
    <p v-if="description" class="empty-state__description">{{ description }}</p>
    <div v-if="$slots.actions" class="empty-state__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 3rem 1.5rem;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  background: var(--color-background-soft);
  text-align: center;
}

.empty-state__title {
  color: var(--color-heading);
  font-weight: 600;
}

.empty-state__description {
  max-width: 32rem;
  color: var(--color-text-muted);
}

.empty-state__actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}
</style>
