import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Story Parts",
        short_name: "Story Parts",
        description: "Split videos locally into social-media-sized parts.",
        theme_color: "#0b1020",
        background_color: "#0b1020",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          {
            src: "/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable"
          }
        ]
      },
      workbox: {
        globIgnores: ["**/vendor/ffmpeg/**"],
        runtimeCaching: [
          {
            urlPattern: /\/vendor\/ffmpeg\/0\.12\.10\//,
            handler: "CacheFirst",
            options: {
              cacheName: "ffmpeg-core-0.12.10",
              expiration: {
                maxEntries: 2,
                maxAgeSeconds: 31_536_000
              }
            }
          }
        ]
      }
    })
  ],
  build: {
    target: "es2022",
    sourcemap: true
  },
  test: {
    include: ["src/**/*.test.ts"],
    coverage: {
      reporter: ["text", "html"]
    }
  }
});
