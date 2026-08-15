<script setup lang="ts">
import { ref } from 'vue'

import { UPLOAD_ACCEPT_ATTRIBUTE, UPLOAD_ACCEPT_EXTENSIONS } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useDocumentsStore } from '@/stores/documents'
import { useToastsStore } from '@/stores/toasts'

/**
 * The two document intake paths of docs/ingestion.md, side by side above the
 * list: a file (dropped or picked) and a URL. Both create a document plus its
 * `parse_document` job; the resulting row and its job id go into the documents
 * store, which is where the list picks the progress up from.
 *
 * A dropped file is checked against the extensions the upload endpoint accepts
 * before it is sent, so an unsupported file fails immediately with a readable
 * message instead of coming back as a 400 from the server.
 */
const { t } = useAppI18n()
const store = useDocumentsStore()
const toasts = useToastsStore()

const uploading = ref(false)
const dragging = ref(false)

const url = ref('')
const importing = ref(false)

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase()
  return UPLOAD_ACCEPT_EXTENSIONS.some((extension) => name.endsWith(extension))
}

async function uploadFile(file: File): Promise<void> {
  if (!isAcceptedFile(file)) {
    toasts.error(t('documents.intake.unsupportedFile', { name: file.name }))
    return
  }
  uploading.value = true
  try {
    const result = await store.upload(file)
    toasts.success(t('documents.intake.uploaded', { title: result.document.title }))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    uploading.value = false
  }
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) {
    return
  }
  const file = input.files?.[0]
  if (file === undefined) {
    return
  }
  await uploadFile(file)
  // Reset the picker so the same file can be uploaded again if needed.
  input.value = ''
}

async function onDrop(event: DragEvent): Promise<void> {
  dragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file === undefined) {
    return
  }
  await uploadFile(file)
}

async function onSubmitUrl(): Promise<void> {
  const trimmed = url.value.trim()
  if (trimmed === '' || importing.value) {
    return
  }
  importing.value = true
  try {
    const result = await store.importUrl(trimmed)
    url.value = ''
    toasts.success(t('documents.intake.imported', { title: result.document.title }))
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <section class="intake">
    <div
      class="intake__drop"
      :class="{ 'is-dragging': dragging, 'is-busy': uploading }"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="dragging = true"
      @dragleave.self="dragging = false"
      @drop.prevent="onDrop"
    >
      <AppIcon class="intake__drop-icon" name="upload" :size="24" />
      <p class="intake__drop-title">{{ t('documents.intake.dropTitle') }}</p>
      <p class="intake__hint">{{ t('documents.intake.fileHint') }}</p>

      <input
        id="document-upload-input"
        class="intake__file-input"
        type="file"
        :accept="UPLOAD_ACCEPT_ATTRIBUTE"
        :disabled="uploading"
        @change="onFileChange"
      />
      <label class="intake__pick" for="document-upload-input">
        {{ uploading ? t('documents.intake.uploading') : t('documents.intake.pickFile') }}
      </label>
    </div>

    <form class="intake__url" @submit.prevent="onSubmitUrl">
      <label class="form-label" for="document-url-input">
        {{ t('documents.intake.urlLabel') }}
      </label>
      <p class="intake__hint">{{ t('documents.intake.urlHint') }}</p>
      <div class="intake__url-row">
        <input
          id="document-url-input"
          v-model="url"
          class="form-input"
          type="url"
          required
          :placeholder="t('documents.intake.urlPlaceholder')"
          :disabled="importing"
        />
        <AppButton type="submit" :disabled="importing || url.trim() === ''">
          {{ importing ? t('documents.intake.importing') : t('documents.intake.urlSubmit') }}
        </AppButton>
      </div>
    </form>
  </section>
</template>

<style scoped>
.intake {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-4);
}

.intake__drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-5);
  border: 1px dashed var(--color-border-hover);
  border-radius: var(--radius-lg);
  background: var(--color-background-soft);
  text-align: center;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.intake__drop.is-dragging {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.intake__drop.is-busy {
  opacity: 0.7;
}

.intake__drop-icon {
  color: var(--color-text-muted);
}

.intake__drop-title {
  color: var(--color-heading);
  font-weight: 600;
}

/* The real input stays in the DOM (and in the accessibility tree via its
   label) but is never the visible control */
.intake__file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.intake__pick {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem 0.9rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-background);
  color: var(--color-heading);
  cursor: pointer;
}

.intake__pick:hover {
  background: var(--color-background-mute);
  border-color: var(--color-border-hover);
}

.intake__file-input:focus-visible + .intake__pick {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.intake__url {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
}

.intake__url-row {
  display: flex;
  gap: var(--space-2);
  margin-top: auto;
}

.intake__hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}
</style>
