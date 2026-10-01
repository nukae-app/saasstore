const tokens = require("./theme.tokens.js");

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: tokens.colors,
      fontFamily: tokens.fontFamily,
      borderRadius: {
        card: `${tokens.radius.card}px`,
        button: `${tokens.radius.button}px`,
        badge: `${tokens.radius.badge}px`,
      },
    },
  },
  plugins: [],
};
