<script setup lang="ts">
import ToastHost from './components/ToastHost.vue'
</script>

<template>
  <div class="app">
    <header class="app__header">
      <div class="app__container app__header-inner">
        <span class="app__brand">KEITARO WRAPPER</span>
        <span class="app__brand-note muted">campaign utility</span>
      </div>
    </header>

    <main class="app__container app__main">
      <router-view />
    </main>

    <ToastHost />
  </div>
</template>

<style scoped>
.app__header {
  border-bottom: 1px solid var(--c-border);
}

.app__header-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 48px;
}

.app__brand {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.app__brand-note {
  font-size: 12px;
}

.app__container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.app__main {
  padding-top: 24px;
  padding-bottom: 48px;
}
</style>
