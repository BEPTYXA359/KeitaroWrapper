<script setup lang="ts">
/** Редактор потоков кампании (в разработке). */

import { useRoute } from 'vue-router'

const route = useRoute()
const uuid = route.params.uuid as string
</script>

<template>
  <section>
    <nav class="streams__crumbs muted">
      <span>Campaigns</span>
      <span class="streams__crumb-sep">/</span>
      <span>campaign</span>
      <span class="streams__crumb-sep">/</span>
      <span class="streams__crumb-current">Keitaro Streams</span>
    </nav>

    <h1 class="page-title streams__title">Keitaro Streams</h1>

    <p class="muted">
      Редактор офферов потока — в разработке.<br />
      Campaign UUID: <span class="mono">{{ uuid }}</span>
    </p>
  </section>
</template>

<style scoped>
.streams__crumbs {
  display: flex;
  align-items: center;
  font-size: 13px;
  margin-bottom: var(--space-4);
}

.streams__crumb-sep {
  padding: 0 4px;
}

.streams__crumb-current {
  color: var(--c-text);
}

.streams__title {
  margin-bottom: var(--space-3);
}
</style>
