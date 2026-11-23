<script setup lang="ts">
/** Автокомплит офферов (/api/offers/search): дропдаун, клавиатура ↑↓/Enter/Esc. */

import { onBeforeUnmount, onMounted, ref } from 'vue'

import { api, ApiError, type OfferSearchItem } from '../api'

withDefaults(
  defineProps<{
    label?: string
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    label: undefined,
    placeholder: 'Поиск оффера по id или названию…',
    disabled: false,
  },
)

const emit = defineEmits<{ select: [offer: OfferSearchItem | null] }>()

const SEARCH_DEBOUNCE_MS = 300

const query = ref('')
const items = ref<OfferSearchItem[]>([])
const open = ref(false)
const activeIndex = ref(-1)
const loading = ref(false)
const searchError = ref('')
const root = ref<HTMLElement | null>(null)

let selected: OfferSearchItem | null = null
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

function clearDebounce(): void {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
}

async function runSearch(): Promise<void> {
  const seq = ++searchSeq
  loading.value = true
  searchError.value = ''
  try {
    const result = await api.searchOffers(query.value.trim())
    if (seq !== searchSeq) return // устаревший ответ
    items.value = result
    activeIndex.value = result.length ? 0 : -1
    open.value = true
  } catch (error) {
    if (seq !== searchSeq) return
    items.value = []
    searchError.value = error instanceof ApiError ? error.detail : 'Не удалось загрузить офферы'
    open.value = true
  } finally {
    if (seq === searchSeq) loading.value = false
  }
}

function onInput(): void {
  if (selected) {
    selected = null
    emit('select', null) // ввод после выбора сбрасывает фиксацию оффера
  }
  clearDebounce()
  debounceTimer = setTimeout(runSearch, SEARCH_DEBOUNCE_MS)
}

function onFocus(): void {
  clearDebounce()
  void runSearch()
}

function choose(offer: OfferSearchItem): void {
  selected = offer
  query.value = offer.name
  open.value = false
  emit('select', offer)
}

function onKeydown(event: KeyboardEvent): void {
  if (!open.value || !items.value.length) {
    if (event.key === 'Escape') open.value = false
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, items.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (event.key === 'Enter') {
    event.preventDefault() // не отправлять форму
    const offer = items.value[activeIndex.value]
    if (offer) choose(offer)
  } else if (event.key === 'Escape') {
    open.value = false
  }
}

function onOutsideClick(event: MouseEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', onOutsideClick))
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onOutsideClick)
  clearDebounce()
})
</script>

<template>
  <div
    ref="root"
    class="autocomplete"
    role="combobox"
    :aria-expanded="open"
    aria-haspopup="listbox"
  >
    <span v-if="label" class="autocomplete__label">{{ label }}</span>
    <input
      v-model="query"
      class="autocomplete__field"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      autocomplete="off"
      @input="onInput"
      @focus="onFocus"
      @keydown="onKeydown"
    />

    <div v-if="open" class="autocomplete__dropdown" role="listbox">
      <p v-if="searchError" class="autocomplete__status autocomplete__status--error">
        {{ searchError }}
      </p>
      <p v-else-if="loading && !items.length" class="autocomplete__status muted">Загрузка…</p>
      <p v-else-if="!items.length" class="autocomplete__status muted">Ничего не найдено</p>
      <button
        v-for="(item, index) in items"
        v-else
        :key="item.id"
        type="button"
        role="option"
        :aria-selected="index === activeIndex"
        class="autocomplete__item"
        :class="{ 'autocomplete__item--active': index === activeIndex }"
        @mouseenter="activeIndex = index"
        @click="choose(item)"
      >
        <span class="autocomplete__id mono">{{ item.id }}</span>
        <span class="autocomplete__name">{{ item.name }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.autocomplete {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.autocomplete__label {
  font-size: 12px;
  font-weight: 500;
}

.autocomplete__field {
  height: var(--control-h);
  padding: 0 12px;
  font-size: 13px;
  color: var(--c-text);
  background: var(--c-bg);
  border: 1px solid var(--c-border-strong);
  border-radius: var(--radius);
}

.autocomplete__field::placeholder {
  color: var(--c-text-faint);
}

.autocomplete__field:focus {
  outline: none;
  box-shadow: 0 0 0 2px var(--c-bg), 0 0 0 4px var(--c-border-strong);
}

.autocomplete__field:disabled {
  opacity: 0.4;
  cursor: default;
}

/* дропдаун: тень только у всплывающих слоёв */
.autocomplete__dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 10;
  max-height: 280px;
  overflow-y: auto;
  background: var(--c-bg);
  border: 1px solid var(--c-border-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow-pop);
}

.autocomplete__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 36px;
  padding: 0 12px;
  font-size: 13px;
  color: var(--c-text);
  text-align: left;
  background: transparent;
  border: none;
}

.autocomplete__id {
  font-size: 12px;
  color: var(--c-text-muted);
  font-variant-numeric: tabular-nums;
}

/* hover / активный элемент клавиатуры — инверсия */
.autocomplete__item--active,
.autocomplete__item:hover {
  background: var(--c-surface-dark);
  color: #fff;
}

.autocomplete__item--active .autocomplete__id,
.autocomplete__item:hover .autocomplete__id {
  color: #d4d4d4;
}

.autocomplete__status {
  padding: 0 12px;
  font-size: 13px;
  line-height: 36px;
}

.autocomplete__status--error {
  color: var(--c-danger);
}
</style>
