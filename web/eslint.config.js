// Deliberately narrow. This is not a style pass — it exists for one class of
// defect that shipped twice: an identifier used in App.jsx whose import was
// never added, which the bundler compiles happily and which only fails when a
// real user opens that screen.
//
// Both escapes came from edits whose import statement silently failed to apply.
// Tests did not catch them because the harness imported the modules directly,
// and the build did not because a missing binding is a runtime ReferenceError.
// `no-undef` catches all of it statically, on every file, every run.
import js from "@eslint/js";

export default [
  {
    files: ["src/**/*.js", "src/**/*.jsx", "tests/**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: "readonly", document: "readonly", navigator: "readonly",
        localStorage: "readonly", sessionStorage: "readonly",
        fetch: "readonly", URL: "readonly", URLSearchParams: "readonly",
        setTimeout: "readonly", clearTimeout: "readonly",
        setInterval: "readonly", clearInterval: "readonly",
        console: "readonly", Intl: "readonly", Buffer: "readonly",
        crypto: "readonly", globalThis: "readonly", process: "readonly",
        requestAnimationFrame: "readonly", cancelAnimationFrame: "readonly",
        __dirname: "readonly", require: "readonly", module: "writable",
        // Vite injects these.
        import: "readonly",
      },
    },
    linterOptions: {
      // The codebase carries react-hooks/exhaustive-deps disable comments from
      // before this config existed. Reporting them as unknown rules would bury
      // the one rule that matters in noise.
      reportUnusedDisableDirectives: false,
    },
    // Declared as a no-op so the existing `// eslint-disable-next-line
    // react-hooks/exhaustive-deps` comments resolve. Those disables are
    // deliberate and predate this config; failing on them would bury the one
    // rule this exists for.
    plugins: { "react-hooks": { rules: { "exhaustive-deps": { create: () => ({}) } } } },
    rules: {
      ...js.configs.recommended.rules,
      // The rule this config exists for.
      "no-undef": "error",
      // Everything else is off: a noisy lint gets ignored, and an ignored lint
      // catches nothing.
      "no-unused-vars": "off",
      "no-empty": "off",
      "no-useless-escape": "off",
      "no-control-regex": "off",
      "no-prototype-builtins": "off",
    },
  },
];
