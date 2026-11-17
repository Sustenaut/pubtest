import { quickpickle } from "quickpickle";
import { defineConfig } from "vitest/config";

// The same features again, run by quickpickle on vitest: pubtest's steps read
// the same under either runner.
export default defineConfig({
  plugins: [quickpickle()],
  test: {
    include: ["features/*.feature"],
    setupFiles: ["test/quickpickle.js"],
    // quickpickle inlined, so vite resolves its imports (pngjs/browser) as Node does not.
    server: { deps: { inline: ["quickpickle"] } },
    // Scenarios share process.env and PATH: one at a time.
    fileParallelism: false,
    testTimeout: 60_000,
  },
});
