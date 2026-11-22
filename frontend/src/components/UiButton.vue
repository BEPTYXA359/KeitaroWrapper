<script setup lang="ts">
/** Кнопка: primary / secondary / danger; md 36px / sm 28px. */

withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'danger'
    size?: 'md' | 'sm'
    type?: 'button' | 'submit'
    disabled?: boolean
    loading?: boolean
  }>(),
  {
    variant: 'secondary',
    size: 'md',
    type: 'button',
    disabled: false,
    loading: false,
  },
)
</script>

<template>
  <button
    class="ui-button"
    :class="[`ui-button--${variant}`, `ui-button--${size}`]"
    :type="type"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="ui-button__spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<style scoped>
.ui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: var(--control-h);
  padding: 0 14px;
  font: 500 13px/1 var(--font-sans);
  color: var(--c-text);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius);
  white-space: nowrap;
  transition:
    background-color 0.12s ease,
    color 0.12s ease,
    border-color 0.12s ease;
}

.ui-button--sm {
  height: var(--control-h-sm);
  padding: 0 10px;
}

.ui-button:disabled {
  opacity: 0.4;
  cursor: default;
}

/* primary: фон тёмный, текст белый, hover #262626 */
.ui-button--primary {
  background: var(--c-surface-dark);
  color: #fff;
}
.ui-button--primary:not(:disabled):hover {
  background: #262626;
}

/* secondary: рамка чёрная, hover — инверсия */
.ui-button--secondary {
  border-color: var(--c-border-strong);
}
.ui-button--secondary:not(:disabled):hover {
  background: var(--c-surface-dark);
  color: #fff;
}

/* danger: рамка/текст красные, hover — заливка */
.ui-button--danger {
  border-color: var(--c-danger);
  color: var(--c-danger);
}
.ui-button--danger:not(:disabled):hover {
  background: var(--c-danger);
  color: #fff;
}

/* loading: ч/б спиннер 14px слева, текст не меняется */
.ui-button__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: ui-button-spin 0.7s linear infinite;
}

@keyframes ui-button-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
