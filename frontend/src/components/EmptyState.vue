<script setup lang="ts">
/**
 * Nothing to show here.
 *
 * One centred line of muted text and, when there is somewhere useful to go, an
 * action under it — no dashed frame and no fill
 * (docs/frontend.md 視覺風格: 不要虛線卡片框; 設計節制原則 D16/D22).
 *
 * `description` is for the rare case where the reason is not obvious from the
 * title (an invalid id in the URL); it is not a subtitle to hang under every
 * empty list. The caller resolves the wording from the locale file and passes
 * it in, so this component contains no text of its own.
 */
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <div class="empty-state">
    <p>{{ title }}</p>
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
  gap: var(--space-2);
  padding: var(--space-6) var(--space-4);
  color: var(--color-text-muted);
  text-align: center;
}

.empty-state__description {
  max-width: var(--reading-max-width);
}

.empty-state__actions {
  display: flex;
  gap: var(--space-3);
}
</style>
