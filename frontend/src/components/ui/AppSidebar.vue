<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useAppI18n } from '@/i18n'
import { NAV_ITEMS } from '@/router/nav'
import AppIcon from './AppIcon.vue'

/**
 * Main navigation.
 *
 * The active item is computed rather than left to `router-link-active`:
 * `/documents/:id` is its own route record with no nav entry of its own, so the
 * built-in classes would leave the navigation unhighlighted while the user sits
 * on a document detail page. `NAV_ITEMS[].matches` maps that route back onto
 * the document entry.
 *
 * `collapsed` is the user's own choice; below the breakpoint in the stylesheet
 * the sidebar collapses to icons regardless. Labels are never removed from the
 * DOM in that state — they are visually hidden — so each link keeps its
 * accessible name.
 */
defineProps<{ collapsed: boolean }>()

const emit = defineEmits<{ toggle: [] }>()

const route = useRoute()
const { t } = useAppI18n()

const activeRouteName = computed(() => {
  const current = route.name
  const item = NAV_ITEMS.find((navItem) => navItem.matches.some((name) => name === current))
  return item?.routeName ?? null
})
</script>

<template>
  <aside class="sidebar" :class="{ 'is-collapsed': collapsed }">
    <RouterLink class="sidebar__brand" :to="{ name: 'dashboard' }">
      <span class="sidebar__mark" aria-hidden="true">Q</span>
      <span class="sidebar__brand-text sidebar__collapsible">{{ t('app.title') }}</span>
    </RouterLink>

    <nav class="sidebar__nav" :aria-label="t('app.navLabel')">
      <RouterLink
        v-for="item in NAV_ITEMS"
        :key="item.routeName"
        class="sidebar__link"
        :class="{ 'is-active': item.routeName === activeRouteName }"
        :aria-current="item.routeName === activeRouteName ? 'page' : undefined"
        :title="t(item.labelKey)"
        :to="{ name: item.routeName }"
      >
        <AppIcon class="sidebar__icon" :name="item.icon" :size="18" />
        <span class="sidebar__collapsible">{{ t(item.labelKey) }}</span>
      </RouterLink>
    </nav>

    <button
      class="sidebar__toggle"
      type="button"
      :aria-label="collapsed ? t('app.expandSidebar') : t('app.collapseSidebar')"
      :aria-pressed="collapsed"
      @click="emit('toggle')"
    >
      <AppIcon :name="collapsed ? 'chevronRight' : 'chevronLeft'" :size="16" />
      <span class="sidebar__collapsible">{{ t('app.collapseSidebar') }}</span>
    </button>
  </aside>
</template>

<style scoped>
.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  height: 100vh;
  padding: var(--space-4) var(--space-3);
  border-right: 1px solid var(--color-border);
  background: var(--color-surface-shell);
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  color: var(--color-heading);
  font-size: var(--font-size-lg);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.sidebar__brand:hover {
  text-decoration: none;
}

.sidebar__mark {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: var(--color-on-accent);
  font-size: var(--font-size-base);
  font-weight: 600;
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-top: var(--space-3);
}

.sidebar__link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-2);
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.sidebar__link:hover {
  background: var(--color-background-mute);
  color: var(--color-heading);
  text-decoration: none;
}

.sidebar__link.is-active {
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
  font-weight: 600;
}

.sidebar__toggle {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: auto;
  padding: var(--space-2);
  border: none;
  border-radius: var(--radius-md);
  background: none;
  color: var(--color-text-faint);
  font: inherit;
  font-size: var(--font-size-md);
  cursor: pointer;
}

.sidebar__toggle:hover {
  background: var(--color-background-mute);
  color: var(--color-heading);
}

/* Collapsed: icons only. The text stays in the accessibility tree so links
   keep their names, and the browser tooltip (`title`) names them visually. */
.sidebar.is-collapsed .sidebar__collapsible {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.sidebar.is-collapsed .sidebar__brand,
.sidebar.is-collapsed .sidebar__link,
.sidebar.is-collapsed .sidebar__toggle {
  justify-content: center;
}

@media (max-width: 1080px) {
  .sidebar .sidebar__collapsible {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .sidebar__brand,
  .sidebar__link,
  .sidebar__toggle {
    justify-content: center;
  }

  /* Below the breakpoint the width is fixed, so there is nothing to toggle */
  .sidebar__toggle {
    display: none;
  }
}
</style>
