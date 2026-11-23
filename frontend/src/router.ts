import { createRouter, createWebHistory } from 'vue-router'

import HomePage from './pages/HomePage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // «Создаватор» кампаний
    { path: '/', name: 'home', component: HomePage },
    // Список кампаний и редактор существующей кампании (лениво — второстепенные страницы)
    {
      path: '/campaigns',
      name: 'campaigns',
      component: () => import('./pages/CampaignsPage.vue'),
    },
    {
      path: '/campaigns/:uuid/streams',
      name: 'streams',
      component: () => import('./pages/StreamsPage.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
