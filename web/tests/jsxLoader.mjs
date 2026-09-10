// Lets node:test import the app's .jsx sources.
//
// Without it nothing could render the real App, and that gap is exactly how two
// missing imports reached a browser: the seed harness imported the extracted
// modules directly, so every panel rendered there while App.jsx had no import
// for them at all.
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { transform } from "esbuild";

export async function load(url, context, nextLoad) {
  // A stylesheet has no meaning outside the bundler; importing one must not be
  // the thing that stops the app being testable.
  if (url.endsWith(".css")) return { format: "module", source: "export default {};", shortCircuit: true };
  if (!url.endsWith(".jsx")) return nextLoad(url, context);
  const source = await readFile(fileURLToPath(url), "utf8");
  const { code } = await transform(source, { loader: "jsx", format: "esm", sourcefile: url });
  return { format: "module", source: code, shortCircuit: true };
}

// The app's own imports are extensionless, as the bundler allows. Node requires
// extensions, so they are resolved here rather than rewritten across the source
// purely to satisfy the test runner.
const EXTENSIONS = [".js", ".jsx"];

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith(".") && !/\.[a-z]+$/i.test(specifier)) {
    for (const extension of EXTENSIONS) {
      try {
        return await nextResolve(`${specifier}${extension}`, context);
      } catch (_) { /* try the next */ }
    }
  }
  return nextResolve(specifier, context);
}
