<script setup lang="ts">
/** Бейдж: neutral / solid (UNSAVED) / danger (REMOVED). */

withDefaults(
  defineProps<{
    variant?: 'neutral' | 'solid' | 'danger'
  }>(),
  { variant: 'neutral' },
)
</script>

<template>
  <span class="ui-badge" :class="`ui-badge--${variant}`">
    <slot />
  </span>
</template>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  font: 500 10px/1 var(--font-sans);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid currentColor;
  border-radius: var(--radius);
  white-space: nowrap;
}

.ui-badge--neutral {
  color: var(--c-text-muted);
}

/* solid — только UNSAVED */
.ui-badge--solid {
  background: var(--c-surface-dark);
  color: #fff;
}

.ui-badge--danger {
  color: var(--c-danger);
}
</style>
