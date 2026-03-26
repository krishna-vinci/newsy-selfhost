#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR="${NEWSY_CERT_DIR:-certs}"
CERT_NAME="${NEWSY_CERT_NAME:-newsy-selfsigned}"
DAYS="${NEWSY_CERT_DAYS:-398}"

if ! command -v openssl >/dev/null 2>&1; then
	echo "error: openssl is required but was not found in PATH" >&2
	exit 1
fi

if [ "$#" -eq 0 ]; then
	set -- localhost 127.0.0.1
fi

mkdir -p "$OUTPUT_DIR"

KEY_PATH="$OUTPUT_DIR/${CERT_NAME}.key"
CERT_PATH="$OUTPUT_DIR/${CERT_NAME}.crt"

TMP_CONFIG="$(mktemp)"
trap 'rm -f "$TMP_CONFIG"' EXIT

is_ip() {
	local value="$1"
	[[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || [[ "$value" == *:* ]]
}

COMMON_NAME="$1"
SAN_LINES=""
DNS_INDEX=1
IP_INDEX=1

for entry in "$@"; do
	if is_ip "$entry"; then
		SAN_LINES+="IP.${IP_INDEX} = ${entry}"$'\n'
		IP_INDEX=$((IP_INDEX + 1))
	else
		SAN_LINES+="DNS.${DNS_INDEX} = ${entry}"$'\n'
		DNS_INDEX=$((DNS_INDEX + 1))
	fi
done

cat > "$TMP_CONFIG" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
CN = ${COMMON_NAME}

[v3_req]
subjectAltName = @alt_names
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
${SAN_LINES}
EOF

openssl req \
	-x509 \
	-nodes \
	-newkey rsa:2048 \
	-sha256 \
	-days "$DAYS" \
	-keyout "$KEY_PATH" \
	-out "$CERT_PATH" \
	-config "$TMP_CONFIG" \
	-extensions v3_req

chmod 600 "$KEY_PATH"

echo "Created self-signed certificate:"
echo "  Cert: $CERT_PATH"
echo "  Key:  $KEY_PATH"
echo
echo "Hostnames / IPs included:"
for entry in "$@"; do
	echo "  - $entry"
done
