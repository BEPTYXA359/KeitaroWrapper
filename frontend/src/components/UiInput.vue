<script setup lang="ts">
/** Инпут: label над полем, ошибка — красная рамка + подпись. */

withDefaults(
  defineProps<{
    label?: string
    placeholder?: string
    error?: string
    hint?: string
    mono?: boolean
    disabled?: boolean
    type?: string
  }>(),
  {
    label: undefined,
    placeholder: undefined,
    error: undefined,
    hint: undefined,
    mono: false,
    disabled: false,
    type: 'text',
  },
)

const model = defineModel<string>({ default: '' })
</script>

<template>
  <label class="ui-input" :class="{ 'ui-input--error': !!error }">
    <span v-if="label" class="ui-input__label">{{ label }}</span>
    <input
      v-model="model"
      class="ui-input__field"
      :class="{ mono: mono }"
      :type="type"
      :placeholder="placeholder"
      :disabled="disabled"
      :aria-invalid="!!error || undefined"
    />
    <span v-if="error" class="ui-input__error">{{ error }}</span>
    <span v-else-if="hint" class="ui-input__hint">{{ hint }}</span>
  </label>
</template>

<style scoped>
.ui-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ui-input__label {
  font-size: 12px;
  font-weight: 500;
}

.ui-input__field {
  height: var(--control-h);
  padding: 0 12px;
  font-size: 13px;
  color: var(--c-text);
  background: var(--c-bg);
  border: 1px solid var(--c-border-strong);
  border-radius: var(--radius);
}

.ui-input__field::placeholder {
  color: var(--c-text-faint);
}

.ui-input__field:focus {
  outline: none;
  box-shadow: 0 0 0 2px var(--c-bg), 0 0 0 4px var(--c-border-strong);
}

.ui-input__field:disabled {
  opacity: 0.4;
  cursor: default;
}

/* ошибка валидации: рамка danger + подпись под полем */
.ui-input--error .ui-input__field {
  border-color: var(--c-danger);
}
.ui-input--error .ui-input__field:focus {
  box-shadow: 0 0 0 2px var(--c-bg), 0 0 0 4px var(--c-danger);
}

.ui-input__error {
  font-size: 12px;
  color: var(--c-danger);
}

.ui-input__hint {
  font-size: 12px;
  color: var(--c-text-muted);
}
</style>
