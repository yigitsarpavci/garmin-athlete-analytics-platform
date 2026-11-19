/** Tailwind CSS 3.4 yapılandırması. Statik CSS üretimi: `make css` (bkz. Makefile). Tarayıcıda Tailwind derleyicisi çalışmaz. */
module.exports = {
  darkMode: 'class',
  content: ['./app/static/index.html', './app/static/js/*.js'],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Newsreader"', 'Georgia', 'serif'],
        sans: ['"Newsreader"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
};
