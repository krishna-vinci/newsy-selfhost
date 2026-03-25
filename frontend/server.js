import fs from 'node:fs';
import https from 'node:https';

import { handler } from './build/handler.js';

const port = Number(process.env.PORT || '3456');
const host = process.env.HOST || '0.0.0.0';
const certPath = process.env.TLS_CERT_FILE || '/app/certs/newsy-selfsigned.crt';
const keyPath = process.env.TLS_KEY_FILE || '/app/certs/newsy-selfsigned.key';

if (!fs.existsSync(certPath) || !fs.existsSync(keyPath)) {
	throw new Error(
		`TLS certificate files are missing. Expected cert at ${certPath} and key at ${keyPath}.`
	);
}

const server = https.createServer(
	{
		cert: fs.readFileSync(certPath),
		key: fs.readFileSync(keyPath)
	},
	handler
);

server.listen(port, host, () => {
	console.log(`newsy frontend listening with HTTPS on https://${host}:${port}`);
	console.log(`Using certificate: ${certPath}`);
});
