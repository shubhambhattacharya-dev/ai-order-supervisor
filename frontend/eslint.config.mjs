import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      // The console intentionally syncs with the backend inside mount effects
      // (initial load + live refresh). React 19 flags this pattern, so the
      // rule is configured off here instead of disabled file by file.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  {
    ignores: ["node_modules/**", ".next/**", "out/**", "next-env.d.ts"],
  },
];

export default eslintConfig;
