<script setup lang="ts">
import { ref, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAppI18n } from '@/i18n'

/**
 * 文件改名 — one small form, used both by a 文件庫 row and by the detail page
 * header (docs/frontend.md: 文件改名於列內動作與詳情頁 header 提供).
 *
 * The dialog only collects the title: the caller performs the `PATCH` so each
 * page can update its own state (the list row, the detail header) and report
 * failures its own way. It therefore stays open while `busy` is true and until
 * the caller closes it, so a rejected title (blank or too long server-side) can
 * be corrected without retyping everything.
 */
const props = defineProps<{
  open: boolean
  /** Current title; refilled every time the dialog opens. */
  title: string
  /** The caller's request is in flight. */
  busy?: boolean
}>()

const emit = defineEmits<{ close: []; submit: [title: string] }>()

const { t } = useAppI18n()

const value = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      value.value = props.title
    }
  },
  { immediate: true },
)

function onSubmit(): void {
  const title = value.value.trim()
  if (title === '' || props.busy === true) {
    return
  }
  emit('submit', title)
}
</script>

<template>
  <AppModal :open="props.open" :title="t('documents.rename.title')" @close="emit('close')">
    <form class="rename" @submit.prevent="onSubmit">
      <label class="form-field">
        <span class="form-label">{{ t('documents.rename.label') }}</span>
        <input
          v-model="value"
          class="form-input"
          type="text"
          :placeholder="t('documents.rename.placeholder')"
        />
      </label>
      <p class="form-hint">{{ t('documents.rename.hint') }}</p>
    </form>

    <template #actions>
      <AppButton variant="secondary" :disabled="props.busy === true" @click="emit('close')">
        {{ t('common.cancel') }}
      </AppButton>
      <AppButton :disabled="value.trim() === '' || props.busy === true" @click="onSubmit">
        {{ props.busy === true ? t('documents.rename.saving') : t('documents.rename.submit') }}
      </AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
/* A form with a single field submits on Enter by itself, which is why the
   field is wrapped in one at all; the visible button sits in the dialog footer */
.rename {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
