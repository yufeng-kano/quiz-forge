<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

/**
 * Old `/conversations` and `/conversations/:id` bookmarks land here and are
 * immediately `replace`d onto `/questions`. A positive integer `:id` is passed
 * as `?conversation=` so the bank page can open that chat in the right column
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D10).
 */
const props = defineProps<{ id?: string }>()

const router = useRouter()

onMounted(() => {
  const parsed = Number(props.id)
  const conversation =
    props.id !== undefined && Number.isInteger(parsed) && parsed > 0 ? String(parsed) : undefined
  void router.replace({
    name: 'questions',
    query: conversation === undefined ? {} : { conversation },
  })
})
</script>

<template>
  <div />
</template>
