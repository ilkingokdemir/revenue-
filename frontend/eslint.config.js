module.exports = [
  {
    ignores: ["build/**", "node_modules/**", "public/**"],
  },
  {
    files: ["**/*.js", "**/*.jsx"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: {
      "react-hooks": require("eslint-plugin-react-hooks"),
    },
    rules: {},
  },
];
