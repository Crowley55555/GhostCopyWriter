#!/bin/bash
# Генерация самоподписанного SSL-сертификата для доступа по IP (без домена).
# Использование: ./deploy/generate-ssl-ip.sh [IP]
# По умолчанию: 85.208.86.148

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_IP="${1:-85.208.86.148}"
SSL_DIR="$PROJECT_DIR/ssl"

echo "Генерация SSL для IP: $SERVER_IP"
mkdir -p "$SSL_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$SSL_DIR/key.pem" \
  -out "$SSL_DIR/cert.pem" \
  -subj "/CN=$SERVER_IP" \
  -addext "subjectAltName=IP:$SERVER_IP"

chmod 600 "$SSL_DIR/key.pem" "$SSL_DIR/cert.pem"

echo "Готово: $SSL_DIR/cert.pem, $SSL_DIR/key.pem"
echo "Сайт: https://$SERVER_IP/ (браузер покажет предупреждение о самоподписанном сертификате)"
