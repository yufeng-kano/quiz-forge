<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'
import { useConfirmHost } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import AppModal from './AppModal.vue'

/**
 * The single confirmation dialog, mounted once in `App.vue`.
 *
 * It renders whatever `useConfirm()` is currently asking; every destructive
 * action in the app therefore looks and behaves identically instead of each
 * view inventing its own inline "are you sure?" row.
 */
const { request, accept, cancel } = useConfirmHost()

const { t } = useAppI18n()

const options = computed(() => request.value?.options ?? null)
</script>

<template>
  <AppModal :open="options !== null" :title="options?.title ?? ''" @close="cancel">
    <p>{{ options?.message }}</p>

    <template #actions>
      <AppButton variant="secondary" @click="cancel">
        {{ options?.cancelLabel ?? t('common.cancel') }}
      </AppButton>
      <AppButton :variant="options?.tone === 'danger' ? 'danger' : 'primary'" @click="accept">
        {{ options?.confirmLabel ?? t('common.confirm') }}
      </AppButton>
    </template>
  </AppModal>
</template>
