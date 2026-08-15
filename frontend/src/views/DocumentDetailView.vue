<script setup lang="ts">
import { useAppI18n } from '@/i18n'

import EmptyState from '@/components/EmptyState.vue'

/** `:id` comes from the router's `props: true`; route params are always strings. */
const props = defineProps<{ id: string }>()

const { t } = useAppI18n()
</script>

<template>
  <section class="page">
    <header class="page-header">
      <h2 class="page-title">{{ t('pages.documentDetail.title') }}</h2>
      <p class="page-subtitle">{{ t('pages.documentDetail.subtitle', { id: props.id }) }}</p>
      <p class="page-description">{{ t('pages.documentDetail.description') }}</p>
    </header>

    <EmptyState :title="t('placeholder.title')" :description="t('placeholder.description')" />
  </section>
</template>
