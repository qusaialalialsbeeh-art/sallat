import path from "path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import { cpSync, mkdirSync } from "fs";

const root = path.resolve(import.meta.dirname);
const ortSource = path.resolve(
  root,
  "node_modules/onnxruntime-web/dist",
);
const ortDestination = path.resolve(
  root,
  "dist/public/ort",
);

const crossOriginHeaders = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
};

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "copy-onnxruntime-wasm",
      closeBundle() {
        mkdirSync(ortDestination, {
          recursive: true,
        });

        const files = [
          "ort-wasm-simd-threaded.wasm",
          "ort-wasm-simd-threaded.mjs",
          "ort-wasm-simd-threaded.asyncify.wasm",
          "ort-wasm-simd-threaded.asyncify.mjs",
          "ort-wasm-simd-threaded.jsep.wasm",
          "ort-wasm-simd-threaded.jsep.mjs",
          "ort-wasm-simd-threaded.jspi.wasm",
          "ort-wasm-simd-threaded.jspi.mjs",
        ];

        for (const file of files) {
          cpSync(
            path.join(ortSource, file),
            path.join(ortDestination, file),
          );
        }

        console.log(
          "ONNX Runtime WASM files copied to /ort/",
        );
      },
    },
  ],

  resolve: {
    alias: {
      "@": path.resolve(
        root,
        "src",
      ),
    },

    dedupe: [
      "react",
      "react-dom",
    ],
  },

  root,

  server: {
    headers: crossOriginHeaders,
  },

  preview: {
    headers: crossOriginHeaders,
  },

  build: {
    outDir: path.resolve(
      root,
      "dist/public",
    ),
    emptyOutDir: true,
  },
});
