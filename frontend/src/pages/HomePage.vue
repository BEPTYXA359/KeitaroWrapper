<script setup lang="ts">
/** Главная: форма «New campaign» + экран «Создано» со ссылками. */

import { onMounted, ref } from 'vue'

import { api, type CreatedCampaignResponse } from '../api'
import CampaignForm from '../components/CampaignForm.vue'
import IconExternalLink from '../components/IconExternalLink.vue'
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
    <div class="page-head">
      <h1 class="page-title">{{ created ? 'Создано' : 'New campaign' }}</h1>
      <UiBadge v-if="backend === 'ok'" variant="neutral">backend ok</UiBadge>
      <UiBadge v-else-if="backend === 'down'" variant="danger">backend down</UiBadge>
      <UiBadge v-else variant="neutral">checking…</UiBadge>
      <div class="page-head__actions">
        <UiButton variant="secondary" href="/campaigns">ALL CAMPAIGNS</UiButton>
      </div>
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
          <IconExternalLink />
        </UiButton>
        <UiButton variant="secondary" :href="`/campaigns/${created.uuid}/streams`">
          OPEN STREAMS
        </UiButton>
      </div>
    </div>
  </section>
</template>

<style scoped>
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
</style>
