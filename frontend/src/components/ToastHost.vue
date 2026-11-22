<script setup lang="ts">
/** Хост тостов: стек снизу вверх, клик — закрыть. */

import { toast, toasts } from '../composables/toast'
</script>

<template>
  <div class="toast-host" aria-live="polite">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast"
      :class="{ 'toast--error': t.kind === 'error' }"
      role="status"
      @click="toast.dismiss(t.id)"
    >
      {{ t.text }}
    </div>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1000;
  display: flex;
  flex-direction: column-reverse; /* стек снизу вверх */
  gap: 8px;
}

.toast {
  max-width: 420px;
  padding: 10px 16px;
  font-size: 13px;
  color: #fff;
  background: var(--c-surface-dark);
  box-shadow: var(--shadow-pop);
  cursor: pointer;
}

.toast:focus-visible {
  box-shadow: 0 0 0 2px var(--c-bg), 0 0 0 4px #fff;
}

/* у ошибки — левая красная полоса 3px */
.toast--error {
  border-left: 3px solid var(--c-danger);
}
</style>
