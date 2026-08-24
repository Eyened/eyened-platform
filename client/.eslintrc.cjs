module.exports = {
  extends: ["eslint:recommended", "@sveltejs/eslint-config-svelte"],
  overrides: [
    {
      files: ["**/*.svelte"],
      rules: {
        "no-restricted-syntax": [
          "error",
          {
            selector: "ExportNamedDeclaration[declaration.kind='let']",
            message: "Use $props() instead of `export let` in runes mode."
          }
        ]
      }
    }
  ]
};
