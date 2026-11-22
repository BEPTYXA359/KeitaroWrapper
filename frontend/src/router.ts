import { createRouter, createWebHistory } from 'vue-router'

import HomePage from './pages/HomePage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // «Создаватор» кампаний
    { path: '/', name: 'home', component: HomePage },
    // Редактор потоков (лениво — второстепенная страница)
    {
      path: '/campaigns/:uuid/streams',
      name: 'streams',
      component: () => import('./pages/StreamsPage.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
