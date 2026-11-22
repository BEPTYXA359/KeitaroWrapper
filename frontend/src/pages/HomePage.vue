<script setup lang="ts">
/** Главная: создание кампаний Keitaro (в разработке). */

import { onMounted, ref } from 'vue'

import { api } from '../api'
import UiBadge from '../components/UiBadge.vue'

const backend = ref<'checking' | 'ok' | 'down'>('checking')

onMounted(async () => {
  try {
    const health = await api.health()
    backend.value = health.status === 'ok' ? 'ok' : 'down'
  } catch {
    backend.value = 'down'
  }
})
</script>

<template>
  <section>
    <div class="home__head">
      <h1 class="page-title">New campaign</h1>
      <UiBadge v-if="backend === 'ok'" variant="neutral">backend ok</UiBadge>
      <UiBadge v-else-if="backend === 'down'" variant="danger">backend down</UiBadge>
      <UiBadge v-else variant="neutral">checking…</UiBadge>
    </div>

    <p class="muted">Форма создания кампаний (name / geo / offer) — в разработке.</p>
  </section>
</template>

<style scoped>
.home__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--space-3);
}
</style>
