// Mina Service Worker for PWA Features
const CACHE_NAME = 'mina-v1';
const urlsToCache = [
  '/',
  '/static/css/modern_design_system.css',
  '/static/css/enhanced_component_library.css',
  '/static/js/modern_ui_interactions.js',
  '/static/js/mobile_enhanced_optimizations.js',
  '/static/js/audio_quality_assessment.js',
  '/static/js/comprehensive_system_validation.js',
  '/static/js/enhanced_websocket_client_v2.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      })
  );
});