<script setup lang="ts">
import { ref } from 'vue'
import { RouterView } from 'vue-router'

import AppSidebar from '@/components/ui/AppSidebar.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import ToastHost from '@/components/ui/ToastHost.vue'

/**
 * Application shell: a left sidebar plus a full-width content region, with the
 * two singleton overlays (confirmation dialog and toast stack) mounted once
 * here rather than by every view that needs them.
 *
 * Each view supplies its own header bar (`PageHeader`) as its first element,
 * so the title and the primary action land on the same line on every route.
 */
const sidebarCollapsed = ref(false)
</script>

<template>
  <div class="app-shell" :class="{ 'is-collapsed': sidebarCollapsed }">
    <AppSidebar :collapsed="sidebarCollapsed" @toggle="sidebarCollapsed = !sidebarCollapsed" />

    <main class="app-main">
      <RouterView />
    </main>

    <ConfirmDialog />
    <ToastHost />
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  /* Hard viewport height so a long workspace list cannot grow the shell
     (docs/decisions/2026-08-17-bank-on-questions-page.md D13). */
  min-height: 100vh;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.app-shell.is-collapsed {
  grid-template-columns: var(--sidebar-width-collapsed) minmax(0, 1fr);
}

/* Flex column so workspace pages can `flex: 1` into the leftover height.
   `overflow: hidden` keeps `/questions` from sharing one scroll frame
   (docs/decisions/2026-08-17-bank-on-questions-page.md D13). Non-workspace
   pages scroll their own `.page` in main.css. */
.app-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  width: 100%;
  max-width: var(--content-max-width);
  padding: 0 var(--content-padding-x) var(--space-7);
  overflow: hidden;
}

/* Same breakpoint as the sidebar's own collapse rule */
@media (max-width: 1080px) {
  .app-shell,
  .app-shell.is-collapsed {
    grid-template-columns: var(--sidebar-width-collapsed) minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .app-main {
    --content-padding-x: var(--space-4);
  }
}
</style>
