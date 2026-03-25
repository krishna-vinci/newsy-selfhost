#!/bin/sh

set -eu

CERT_DIR="${TLS_CERT_DIR:-/app/certs}"
CERT_FILE="${TLS_CERT_FILE:-$CERT_DIR/newsy-selfsigned.crt}"
KEY_FILE="${TLS_KEY_FILE:-$CERT_DIR/newsy-selfsigned.key}"
EXTRA_TLS_HOSTS="${TLS_EXTRA_HOSTS:-}"
TLS_CERT_DAYS="${TLS_CERT_DAYS:-398}"

mkdir -p "$CERT_DIR"

PUBLIC_HOST="localhost"
HOSTS="localhost 127.0.0.1 $EXTRA_TLS_HOSTS"

cert_has_required_sans() {
	[ -f "$CERT_FILE" ] || return 1
	CERT_TEXT="$(openssl x509 -in "$CERT_FILE" -noout -text 2>/dev/null || true)"
	[ -n "$CERT_TEXT" ] || return 1

	for entry in $HOSTS; do
		[ -n "$entry" ] || continue
		clean_entry="$(printf '%s' "$entry" | sed 's/^\[//; s/\]$//')"
		if printf '%s' "$clean_entry" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}$|:'; then
			printf '%s' "$CERT_TEXT" | grep -F "IP Address:${clean_entry}" >/dev/null || return 1
		else
			printf '%s' "$CERT_TEXT" | grep -F "DNS:${clean_entry}" >/dev/null || return 1
		fi
	done

	return 0
}


if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ] || ! cert_has_required_sans; then
	TMP_CONFIG="$(mktemp)"

	DNS_INDEX=1
	IP_INDEX=1
	SAN_LINES=""
	SEEN_HOSTS=""

	for entry in $HOSTS; do
		[ -n "$entry" ] || continue
		entry="$(printf '%s' "$entry" | sed 's/^\[//; s/\]$//')"
		case " $SEEN_HOSTS " in
			*" $entry "*)
				continue
				;;
		esac
		SEEN_HOSTS="$SEEN_HOSTS $entry"
		if printf '%s' "$entry" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}$|:'; then
			SAN_LINES="${SAN_LINES}IP.${IP_INDEX} = ${entry}\n"
			IP_INDEX=$((IP_INDEX + 1))
		else
			SAN_LINES="${SAN_LINES}DNS.${DNS_INDEX} = ${entry}\n"
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
CN = ${PUBLIC_HOST}

[v3_req]
subjectAltName = @alt_names
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
$(printf "%b" "$SAN_LINES")
EOF

	openssl req \
		-x509 \
		-nodes \
		-newkey rsa:2048 \
		-sha256 \
		-days "$TLS_CERT_DAYS" \
		-keyout "$KEY_FILE" \
		-out "$CERT_FILE" \
		-config "$TMP_CONFIG" \
		-extensions v3_req

	rm -f "$TMP_CONFIG"

	chmod 600 "$KEY_FILE"
	echo "Generated self-signed TLS certificate at $CERT_FILE"
	printf 'Certificate SANs: %s\n' "$HOSTS"
fi

exec node server.js
