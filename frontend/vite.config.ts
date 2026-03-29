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
const apiBaseUrl = process.env.API_BASE_URL || 'http://127.0.0.1:8765';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		port: 3456,
		allowedHosts,
		proxy: {
			'/api': {
				target: apiBaseUrl,
				changeOrigin: true
			}
		}
	}
});
