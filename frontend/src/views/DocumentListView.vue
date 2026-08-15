<script setup lang="ts">
import { useAppI18n } from '@/i18n'

import EmptyState from '@/components/EmptyState.vue'

const { t } = useAppI18n()
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h2 class="page-title">{{ t('pages.documents.title') }}</h2>
      <p class="page-description">{{ t('pages.documents.description') }}</p>
    </header>

    <EmptyState :title="t('placeholder.title')" :description="t('placeholder.description')" />
  </section>
</template>
