<script setup lang="ts">
import { ref } from 'vue'

import { UPLOAD_ACCEPT_ATTRIBUTE } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'

/**
 * The two document intake paths of docs/ingestion.md: a file upload and a URL
 * import. Both create a document plus its `parse_document` job; the resulting
 * row (and its job id) goes into the documents store, which is where the list
 * picks the progress up from.
 */
const { t } = useAppI18n()
const store = useDocumentsStore()

const uploading = ref(false)
const uploadError = ref<string | null>(null)

const url = ref('')
const importing = ref(false)
const importError = ref<string | null>(null)

async function onFileChange(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) {
    return
  }
  const file = input.files?.[0]
  if (file === undefined) {
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    await store.upload(file)
    // Reset the picker so the same file can be uploaded again if needed.
    input.value = ''
  } catch (error) {
    uploadError.value = translateApiError(error)
  } finally {
    uploading.value = false
  }
}

async function onSubmitUrl(): Promise<void> {
  const trimmed = url.value.trim()
  if (trimmed === '' || importing.value) {
    return
  }
  importing.value = true
  importError.value = null
  try {
    await store.importUrl(trimmed)
    url.value = ''
  } catch (error) {
    importError.value = translateApiError(error)
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <section class="intake">
    <h3 class="intake__title">{{ t('documents.intake.title') }}</h3>

    <div class="intake__grid">
      <div class="intake__field">
        <label class="intake__label" for="document-upload-input">
          {{ t('documents.intake.fileLabel') }}
        </label>
        <input
          id="document-upload-input"
          class="intake__file"
          type="file"
          :accept="UPLOAD_ACCEPT_ATTRIBUTE"
          :disabled="uploading"
          @change="onFileChange"
        />
        <p class="intake__hint">{{ t('documents.intake.fileHint') }}</p>
        <p v-if="uploading" class="intake__hint">{{ t('documents.intake.uploading') }}</p>
        <p v-if="uploadError !== null" class="intake__error">{{ uploadError }}</p>
      </div>

      <form class="intake__field" @submit.prevent="onSubmitUrl">
        <label class="intake__label" for="document-url-input">
          {{ t('documents.intake.urlLabel') }}
        </label>
        <div class="intake__url-row">
          <input
            id="document-url-input"
            v-model="url"
            class="intake__input"
            type="url"
            required
            :placeholder="t('documents.intake.urlPlaceholder')"
            :disabled="importing"
          />
          <AppButton type="submit" :disabled="importing || url.trim() === ''">
            {{ t('documents.intake.urlSubmit') }}
          </AppButton>
        </div>
        <p v-if="importing" class="intake__hint">{{ t('documents.intake.importing') }}</p>
        <p v-if="importError !== null" class="intake__error">{{ importError }}</p>
      </form>
    </div>
  </section>
</template>

<style scoped>
.intake {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background-soft);
}

.intake__title {
  font-size: 1rem;
}

.intake__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1.25rem 2rem;
}

.intake__field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.intake__label {
  color: var(--color-heading);
  font-weight: 600;
}

.intake__url-row {
  display: flex;
  gap: 0.5rem;
}

.intake__input {
  flex: 1;
  min-width: 0;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  color: var(--color-text);
  font: inherit;
}

.intake__input:focus {
  border-color: var(--color-accent);
  outline: none;
}

.intake__file {
  font: inherit;
  color: var(--color-text);
}

.intake__hint {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.intake__error {
  color: var(--color-status-failed-text);
  font-size: 0.875rem;
}
</style>
