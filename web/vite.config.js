import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: import.meta.dirname,
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        configure: (proxy) => proxy.on("proxyReq", (proxyReq) => {
          proxyReq.setHeader("Origin", "http://127.0.0.1:8001");
        }),
      },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
