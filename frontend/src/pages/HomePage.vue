<script setup lang="ts">
/** Главная: форма «New campaign» + экран «Создано» со ссылками. */

import { onMounted, ref } from 'vue'

import { api, type CreatedCampaignResponse } from '../api'
import CampaignForm from '../components/CampaignForm.vue'
import UiBadge from '../components/UiBadge.vue'
import UiButton from '../components/UiButton.vue'

const backend = ref<'checking' | 'ok' | 'down'>('checking')
const created = ref<CreatedCampaignResponse | null>(null)

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
      <h1 class="page-title">{{ created ? 'Создано' : 'New campaign' }}</h1>
      <UiBadge v-if="backend === 'ok'" variant="neutral">backend ok</UiBadge>
      <UiBadge v-else-if="backend === 'down'" variant="danger">backend down</UiBadge>
      <UiBadge v-else variant="neutral">checking…</UiBadge>
    </div>

    <CampaignForm v-if="!created" @created="created = $event" />

    <div v-else class="home__success">
      <p class="home__success-name">{{ created.name }}</p>
      <p class="mono muted home__success-meta">
        keitaro id {{ created.keitaro_campaign_id }} · streams created {{ created.streams_created }}
      </p>
      <div class="home__success-actions">
        <UiButton variant="secondary" :href="created.admin_url" external>
          VIEW IN KT
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </UiButton>
        <UiButton variant="secondary" :href="`/campaigns/${created.uuid}/streams`">
          OPEN STREAMS
        </UiButton>
      </div>
    </div>
  </section>
</template>

<style scoped>
.home__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--space-3);
}

.home__success {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
}

.home__success-name {
  font-size: 14px;
  font-weight: 600;
}

.home__success-meta {
  font-size: 13px;
}

.home__success-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.icon {
  width: 14px;
  height: 14px;
}
</style>
