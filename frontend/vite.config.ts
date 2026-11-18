import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
      proxy: {
        '/api': {
          target: process.env.VITE_API_BASE || 'https://wmb-web-dvkcxrfe6q-ew.a.run.app',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: '../app/watchmybusiness/static',
      emptyOutDir: true,
    },
  };
});
