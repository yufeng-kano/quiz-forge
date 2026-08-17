<script setup lang="ts">
import { computed } from 'vue'

import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import { useAppI18n } from '@/i18n'
import { questionTypeLabel } from '@/questions/labels'
import { questionPreview } from '@/questions/preview'
import { useBankAgentStore } from '@/stores/bankAgent'
import { useExportSelectionStore } from '@/stores/exportSelection'

/**
 * One proposed question, compact: type, id and a single-line stem preview
 * with the full text in its tooltip (docs/frontend.md 清單有界原則).
 *
 * A click asks the bank page to show this question on the left. It never
 * writes the export selection — the person looks at the full card and ticks
 * the checkbox themselves (docs/decisions/2026-08-17-bank-on-questions-page.md
 * D14).
 */
const props = defineProps<{ questionId: number }>()

const emit = defineEmits<{ open: [questionId: number] }>()

const { t } = useAppI18n()
const store = useBankAgentStore()
const selection = useExportSelectionStore()

const question = computed(() => store.proposedQuestion(props.questionId))

const selected = computed(() => selection.isSelected(props.questionId))

const preview = computed(() => {
  const item = question.value
  return item === undefined || item === null ? '' : questionPreview(item)
})

const canOpen = computed(() => question.value !== undefined && question.value !== null)

function onOpen(): void {
  if (!canOpen.value) {
    return
  }
  emit('open', props.questionId)
}
</script>

<template>
  <article class="proposal">
    <template v-if="question === undefined">
      <AppSkeleton width="35%" />
      <AppSkeleton width="80%" />
    </template>

    <p v-else-if="question === null" class="proposal__missing">
      {{ t('bankAgent.proposals.missing', { id: questionId }) }}
    </p>

    <button
      v-else
      class="proposal__open"
      type="button"
      :aria-label="t('bankAgent.proposals.open', { id: question.id })"
      @click="onOpen"
    >
      <span class="proposal__head">
        <span class="proposal__type">{{ questionTypeLabel(question.type) }}</span>
        <span class="proposal__meta">#{{ question.id }}</span>
        <span v-if="selected" class="proposal__selected">
          {{ t('bankAgent.proposals.alreadySelected') }}
        </span>
      </span>
      <span class="proposal__preview text-ellipsis" :title="preview">{{ preview }}</span>
    </button>
  </article>
</template>

<style scoped>
.proposal {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0;
}

.proposal__open {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: 100%;
  min-width: 0;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.proposal__open:hover .proposal__preview {
  color: var(--color-heading);
}

.proposal__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.proposal__type {
  color: var(--color-heading);
  font-size: var(--font-size-md);
  font-weight: 600;
  white-space: nowrap;
}

.proposal__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.proposal__selected {
  margin-left: auto;
  color: var(--color-text-faint);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.proposal__preview {
  max-width: 100%;
  color: var(--color-text);
  font-size: var(--font-size-md);
}

.proposal__missing {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}
</style>
