const reactHooksStub = {
  rules: { "exhaustive-deps": { create: () => ({}) }, "rules-of-hooks": { create: () => ({}) } },
};

module.exports = [
  {
    ignores: [
      "**/node_modules/**",
      "frontend/build/**",
      "frontend/public/**",
      "backend/**",
      "memory/**",
      "test_reports/**",
    ],
  },
  {
    files: ["**/*.js", "**/*.jsx"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: {
      "react-hooks": reactHooksStub,
    },
    linterOptions: {
      reportUnusedDisableDirectives: "off",
    },
    rules: {},
  },
];
