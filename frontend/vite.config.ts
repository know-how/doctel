import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react-swc"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const apiTarget = (env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "")
  const proxyConfig = {
    target: apiTarget,
    changeOrigin: true,
    secure: false,
  } as const

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": proxyConfig,
        "/auth": proxyConfig,
        "/admin": proxyConfig,
        "/users": proxyConfig,
        "/documents": proxyConfig,
        "/projects": proxyConfig,
        "/healthz": proxyConfig,
        "/ws": { ...proxyConfig, ws: true },
      },
    },
  }
})

