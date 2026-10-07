import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// اختبارات الوحدات الخالصة (دوال بلا DOM) — محرر القصاصات.
// التشغيل: npm run test  (vitest run)
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/__tests__/**/*.test.ts"],
  },
});
