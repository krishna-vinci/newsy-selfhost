import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

function parseAllowedHosts(value?: string): true | string[] | undefined {
	if (!value) return undefined;

	const hosts = value
		.split(',')
		.map((host) => host.trim())
		.filter(Boolean);

	if (hosts.includes('*')) {
		return true;
	}

	return hosts.length > 0 ? hosts : undefined;
}

const allowedHosts = parseAllowedHosts(process.env.DEV_ALLOWED_HOSTS);

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		port: 3456,
		allowedHosts,
		proxy: {
			'/api': {
				target: 'http://newsy-backend:8765',
				changeOrigin: true
			}
		}
	}
});
