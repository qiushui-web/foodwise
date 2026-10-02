import { defineConfig } from "vite";
import { resolve } from "path";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  root: "src",
  base: "./",
  plugins: [vue()],
  build: {
    outDir: resolve(__dirname, "..", "src", "main", "resources", "static", "build"),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        app: resolve(__dirname, "src", "app.ts"),
      },
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "vendor.js",
        assetFileNames: "[name][extname]",
      },
    },
    minify: "esbuild",
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
