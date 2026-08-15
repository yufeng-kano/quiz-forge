<script setup lang="ts">
import { computed } from 'vue'

import { ICON_PATHS, type IconName } from './icons'

/**
 * One inline SVG icon from `icons.ts`.
 *
 * The icon is decorative in every current use (it always sits next to a text
 * label or inside a button that carries its own `aria-label`), so it is hidden
 * from assistive technology.
 */
const props = withDefaults(defineProps<{ name: IconName; size?: number }>(), { size: 18 })

const paths = computed<readonly string[]>(() => ICON_PATHS[props.name])
</script>

<template>
  <svg
    class="app-icon"
    :width="props.size"
    :height="props.size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(d, index) in paths" :key="index" :d="d" />
  </svg>
</template>

<style scoped>
.app-icon {
  flex: none;
  display: block;
}
</style>
