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
  min-height: 100vh;
}

.app-shell.is-collapsed {
  grid-template-columns: var(--sidebar-width-collapsed) minmax(0, 1fr);
}

.app-main {
  min-width: 0;
  width: 100%;
  max-width: var(--content-max-width);
  padding: 0 var(--content-padding-x) var(--space-7);
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
