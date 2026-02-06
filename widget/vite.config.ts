import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: 'src/main.tsx',
      name: 'SupportWidget',
      fileName: 'widget',
      formats: ['iife'],
    },
    rollupOptions: {
      output: {
        // Bundle everything into a single file
        inlineDynamicImports: true,
      },
    },
    // Output to static folder for serving
    outDir: '../src/static',
    emptyOutDir: false,
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
});
