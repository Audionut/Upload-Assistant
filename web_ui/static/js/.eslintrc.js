module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    ecmaFeatures: { jsx: true }
  },
  plugins: ["react", "react-hooks"],
  extends: ["eslint:recommended", "plugin:react/recommended"],
  rules: {
    // project-specific overrides
    'react/prop-types': 'off'
    ,
    // New JSX transform doesn't require React in scope
    'react/react-in-jsx-scope': 'off'
  },
  settings: { react: { version: "detect" } },
  globals: {
    React: 'readonly',
    ReactDOM: 'readonly',
    DOMPurify: 'readonly',
    QRCode: 'readonly',
    API_BASE: 'readonly'
  }
};
