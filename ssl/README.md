# SSL для production (HTTPS на порту 443)

В этой папке лежат сертификаты для Nginx в Docker. Файлы `*.pem` **не коммитятся** в Git (см. `.gitignore`).

## Создание сертификата (доступ по IP без домена)

Из корня проекта на сервере:

```bash
bash deploy/generate-ssl-ip.sh              # IP по умолчанию: 85.208.86.148
bash deploy/generate-ssl-ip.sh 203.0.113.10   # свой IP
```

Будут созданы:

- `ssl/cert.pem` — сертификат (SAN `IP:ваш_ip`)
- `ssl/key.pem` — приватный ключ (`chmod 600`)

Затем запустите или перезапустите production-стек:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

## Проверка

```bash
curl -Ik https://ВАШ_IP/
```

В браузере откройте `https://ВАШ_IP` и примите предупреждение о самоподписанном сертификате.

## Домен и Let's Encrypt

Для доверенного HTTPS привяжите домен, получите сертификат (certbot) и положите файлы в `ssl/` или обновите пути в `nginx.prod.conf`. В `.env` задайте `SITE_URL=https://ваш-домен.ru` и `SECURE_HSTS_SECONDS=31536000`.

Подробнее: [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md).
