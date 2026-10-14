# Endpoint sin caché (Cloudflare Workers + KV)

Sirve el JSON de resultados con `Cache-Control: no-store` para que el dashboard
de GitHub Pages pueda mostrar datos frescos ~cada minuto.

## 1. Requisitos
```bash
npm install -g wrangler
wrangler login
```

## 2. Crear el almacén KV
```bash
wrangler kv namespace create ESCUTINIO
```
Copia el `id` que devuelve y pégalo en `wrangler.toml`.

## 3. Definir el token secreto de escritura
```bash
wrangler secret put PUBLISH_TOKEN
# pega un token largo y aleatorio cuando lo pida
```

## 4. Desplegar
```bash
wrangler deploy
```
Te dará una URL tipo:
`https://escrutinio-2026.TU-SUBDOMINIO.workers.dev`

## 5. Configurar el publicador local
En tu máquina (PowerShell):
```powershell
$env:PUBLISH_URL   = "https://escrutinio-2026.TU-SUBDOMINIO.workers.dev/datos"
$env:PUBLISH_TOKEN = "el-mismo-token-del-paso-3"
python runner_local.py
```

## 6. Apuntar el dashboard a este endpoint
Edita `config.js` en la raíz del repositorio:
```js
window.DATOS_URL = "https://escrutinio-2026.TU-SUBDOMINIO.workers.dev/datos";
```

## Notas
- El `GET` es público (solo lectura) y abre CORS a cualquier origen.
- El `PUT` exige `Authorization: Bearer <PUBLISH_TOKEN>`.
- ¿Prefieres otro proveedor? El publicador es genérico: cualquier endpoint que
  acepte un `PUT`/`POST` con JSON y `Authorization: Bearer` sirve (Vercel,
  Supabase, un VPS, etc.). Solo cambia `PUBLISH_URL`/`PUBLISH_METHOD`.
