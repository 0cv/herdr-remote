import { fileURLToPath, URL } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import versions from './build-versions.json';

function stableReleaseAssets(): Plugin {
  return {
    name: 'stable-release-assets',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const javascript = Object.values(bundle).filter(
        (item) => item.type === 'chunk' && item.fileName.endsWith('.js'),
      );
      const stylesheets = Object.values(bundle).filter(
        (item) => item.type === 'asset' && item.fileName.endsWith('.css'),
      );
      if (javascript.length !== 1 || javascript[0]?.fileName !== 'assets/app.js') {
        this.error(`Expected only assets/app.js; found ${javascript.map((item) => item.fileName).join(', ')}`);
      }
      if (stylesheets.length !== 1 || stylesheets[0]?.fileName !== 'assets/app.css') {
        this.error(`Expected only assets/app.css; found ${stylesheets.map((item) => item.fileName).join(', ')}`);
      }

      const html = bundle['index.html'];
      if (!html || html.type !== 'asset' || typeof html.source !== 'string') {
        this.error('Vite did not emit index.html');
      }
      const versioned = html.source
        .replace(/(assets\/app\.js)(?!\?v=)/g, `$1?v=${versions.assets}`)
        .replace(/(assets\/app\.css)(?!\?v=)/g, `$1?v=${versions.assets}`);
      if (!versioned.includes(`assets/app.js?v=${versions.assets}`)) {
        this.error('Generated index.html does not reference the versioned application script');
      }
      if (!versioned.includes(`assets/app.css?v=${versions.assets}`)) {
        this.error('Generated index.html does not reference the versioned application stylesheet');
      }
      html.source = versioned;
    },
  };
}

export default defineConfig({
  plugins: [tailwindcss(), svelte(), stableReleaseAssets()],
  resolve: {
    alias: {
      $lib: fileURLToPath(new URL('./src/lib', import.meta.url)),
      $components: fileURLToPath(new URL('./src/components', import.meta.url)),
    },
    conditions: ['browser'],
  },
  build: {
    cssCodeSplit: false,
    emptyOutDir: true,
    outDir: 'dist',
    rollupOptions: {
      output: {
        assetFileNames: (asset) => {
          const names = asset.names ?? [];
          return names.some((name) => name.endsWith('.css')) ? 'assets/app.css' : 'assets/[name][extname]';
        },
        chunkFileNames: 'assets/[name].js',
        entryFileNames: 'assets/app.js',
      },
    },
    target: 'es2022',
  },
  define: {
    __APP_PROTOCOL_VERSION__: '2',
    __SERVICE_WORKER_URL__: JSON.stringify(`sw.js?v=${versions.serviceWorker}`),
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts'],
    setupFiles: ['./tests/setup.ts'],
  },
});
