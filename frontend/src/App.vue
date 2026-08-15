<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="app-header">
    <h1 class="app-title">QuizForge</h1>

    <nav class="app-nav">
      <RouterLink to="/">Home</RouterLink>
      <RouterLink to="/about">About</RouterLink>
    </nav>
  </header>

  <main class="app-main">
    <RouterView />
  </main>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1.5rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.app-title {
  font-size: 1.25rem;
}

.app-nav {
  display: flex;
  gap: 1.25rem;
}

.app-nav a.router-link-exact-active {
  color: var(--color-heading);
}

.app-main {
  padding-top: var(--section-gap);
}
</style>
