<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useAppI18n } from '@/i18n'

import { NAV_ITEMS } from '@/router/nav'

const route = useRoute()
const { t } = useAppI18n()

/**
 * The active item is computed rather than left to `router-link-active`.
 * `/documents/:id` is its own route record and has no nav entry of its own, so
 * the built-in classes would leave the whole navigation unhighlighted while the
 * user sits on a document detail page. `NAV_ITEMS[].matches` maps that route
 * back onto the document list entry.
 */
const activeRouteName = computed(() => {
  const current = route.name
  const item = NAV_ITEMS.find((navItem) => navItem.matches.some((name) => name === current))
  return item?.routeName ?? null
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="app-brand" :to="{ name: 'documents' }">{{ t('app.title') }}</RouterLink>

      <nav class="app-nav" :aria-label="t('app.navLabel')">
        <RouterLink
          v-for="item in NAV_ITEMS"
          :key="item.routeName"
          class="app-nav-link"
          :class="{ 'is-active': item.routeName === activeRouteName }"
          :aria-current="item.routeName === activeRouteName ? 'page' : undefined"
          :to="{ name: item.routeName }"
        >
          {{ t(item.labelKey) }}
        </RouterLink>
      </nav>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem 2rem;
  padding: 0.9rem 2rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
}

.app-brand {
  color: var(--color-heading);
  font-size: 1.0625rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.app-brand:hover {
  text-decoration: none;
}

.app-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.app-nav-link {
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  color: var(--color-text-muted);
}

.app-nav-link:hover {
  color: var(--color-heading);
  background: var(--color-background-mute);
  text-decoration: none;
}

.app-nav-link.is-active {
  color: var(--color-accent-strong);
  background: var(--color-accent-soft);
}

.app-main {
  flex: 1;
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--section-gap) 2rem 4rem;
}

@media (max-width: 640px) {
  .app-header {
    padding: 0.9rem 1rem;
  }

  .app-main {
    padding: 1.5rem 1rem 3rem;
  }
}
</style>
