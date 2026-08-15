<script setup lang="ts">
import { useAppI18n } from '@/i18n'

import EmptyState from '@/components/EmptyState.vue'

const { t } = useAppI18n()
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h2 class="page-title">{{ t('pages.exports.title') }}</h2>
      <p class="page-description">{{ t('pages.exports.description') }}</p>
    </header>

    <EmptyState :title="t('placeholder.title')" :description="t('placeholder.description')" />
  </section>
</template>
