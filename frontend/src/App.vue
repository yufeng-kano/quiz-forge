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

/* Flex column so workspace pages can `flex: 1` into the leftover height, and
   the scroll frame for the pages that keep their natural height instead.
   A workspace page is exactly as tall as this column and clips itself, so it
   can never turn this into a scroll frame shared with the 題庫 columns
   (docs/decisions/2026-08-17-bank-on-questions-page.md D13).

   The content region's gutter is padding of `.page` (main.css), not of this
   column: `PageHeader` bleeds across the gutter with a negative margin, and
   that bleed only stays inside the scroll frame while the gutter belongs to a
   box the header sits inside. There is no bottom padding here either — that
   band would sit under a workspace page and leave it short of the viewport. */
.app-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  width: 100%;
  max-width: var(--content-max-width);
  overflow-y: auto;
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
