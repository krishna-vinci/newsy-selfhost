import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		port: 3456,
		proxy: {
			'/api': {
				target: 'http://newsy-backend:8765',
				changeOrigin: true
			}
		}
	}
});
