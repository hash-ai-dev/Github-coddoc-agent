/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/renderer/index.html",
        "./src/renderer/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                background: '#0f172a', // slate-900
                surface: '#1e293b', // slate-800
                primary: '#3b82f6', // blue-500
                secondary: '#f59e0b', // amber-500
            }
        },
    },
    plugins: [
        require('@tailwindcss/typography'),
    ],
}
