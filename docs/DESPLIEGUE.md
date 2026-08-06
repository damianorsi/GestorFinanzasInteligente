# Exponer la aplicación

Cómo publicar el proyecto para que otras personas lo prueben desde internet.

> Para levantarlo en tu máquina y nada más, la guía es
> [`INSTALACION.md`](INSTALACION.md). Este documento es para **exponerlo hacia afuera**.

---

## 1. Antes que nada: el compose de desarrollo no se expone

`docker-compose.yml` está pensado para trabajar, no para publicar:

- construye la imagen con el stage `dev`, que trae el toolchain de build;
- monta el código fuente y corre uvicorn con `--reload`;
- **publica MySQL en el puerto 3306 del host**.

Ese último punto es el grave: en una máquina alcanzable desde internet, es dejar la base
de datos abierta al mundo.

Para exponer se usa **`docker-compose.prod.yml`**, que es un archivo **completo, no un
override**:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

> Tiene que ser un archivo aparte y no un `-f base -f override`: al mergear, compose
> **agrega** a las listas de `ports` y `volumes` en vez de reemplazarlas, así que un
> override no podría quitar el 3306 publicado. Con un archivo propio no hay forma de
> heredarlo por descuido.

Qué cambia respecto del de desarrollo:

| | Desarrollo | Expuesto |
|---|---|---|
| Imagen del backend | `dev` (con toolchain) | `runtime`, sin toolchain y con usuario no-root |
| Código | montado, con `--reload` | horneado en la imagen, inmutable |
| MySQL | publicado en el host | **solo en la red interna** |
| Backend | publicado en el 8000 | **solo detrás del proxy** |
| Frontend | `0.0.0.0:8080` | **`127.0.0.1:8080`** |
| `APP_ENV` | `development` | `production` |
| Workers de uvicorn | 1 | **1, obligatorio** |

El worker único no es una elección de performance: el job de recurrentes corre in-process,
y con dos workers habría dos schedulers disparando el mismo job.

Como el backend no se publica, **`/docs` y `/openapi.json` tampoco quedan expuestos**. Es
deliberado. Si necesitás la documentación de la API desde afuera, hay que publicarlos a
propósito.

### Lo que valida `APP_ENV=production`

La aplicación **se niega a arrancar** si:

- `JWT_SECRET_KEY` es el valor de ejemplo o tiene menos de 32 caracteres;
- `ARGON2_TIME_COST` es menor a 2;
- `ARGON2_MEMORY_COST_KIB` es menor a 19456.

Es a propósito: arrastrar por descuido la configuración de tests dejaría las contraseñas
con un hashing barato de romper y nada lo delataría en runtime.

---

## 2. Demo rápida con Cloudflare Tunnel

Sirve para que un grupo pruebe la aplicación **sin contratar nada y sin abrir puertos en
el router**. El túnel sale desde tu máquina hacia Cloudflare, que publica una URL con
HTTPS.

### Instalar

```powershell
winget install --id Cloudflare.cloudflared
```

En macOS: `brew install cloudflared`. En Linux, el `.deb`/`.rpm` de las releases del
proyecto.

### Levantar

```bash
docker compose -f docker-compose.prod.yml up -d --build
cloudflared tunnel --url http://localhost:8080
```

En la salida aparece la URL pública:

```
INF |  https://algo-al-azar.trycloudflare.com  |
```

Esa es la que se comparte. El túnel apunta al **frontend**, que es quien proxea `/api` al
backend: una sola URL, mismo origen, sin CORS.

### Verificar antes de compartir

```bash
curl https://TU-URL.trycloudflare.com/health
```

Tiene que decir `"environment": "production"`. Si dice `"development"`, estás exponiendo
el stack de desarrollo: bajalo y levantá el de producción.

### Límites de este modo

- **La URL cambia cada vez** que arrancás el túnel. Los quick tunnels son anónimos y
  efímeros; para una URL fija hace falta una cuenta de Cloudflare y un dominio propio
  (`cloudflared tunnel create`).
- **Solo funciona con tu máquina prendida** y el proceso corriendo. Si la suspendés, se
  cae.
- Todo el tráfico pasa por tu conexión.

### Cortar

Cerrá el proceso de `cloudflared` (Ctrl+C) y la URL deja de existir al instante. Después:

```bash
docker compose -f docker-compose.prod.yml down
```

---

## 3. Qué tener en cuenta al exponerlo

**El registro es abierto.** Cualquiera con la URL puede crearse una cuenta. Para un grupo
cerrado, lo razonable es no publicar el link más allá de quienes tienen que probarlo, o
poner autenticación básica en un proxy delante.

**Cuidado con la API key de OpenAI.** Si cargás una clave real, cada cuenta que se
registre puede consumirla. El cupo de `CHAT_RATE_LIMIT_PER_HOUR` es **por usuario**, no
global: no hay techo de gasto en la aplicación. Para una demo conviene dejar la clave
dummy —el asistente responde con el mensaje de fallback y todo lo demás funciona— o
configurar un límite de gasto en la cuenta de OpenAI.

**Los datos son reales para quien los carga.** Es una demo, pero si alguien carga sus
finanzas de verdad, están en tu máquina. Avisá que es descartable.

**Sin backup.** El volumen `db_data` no se respalda solo. `docker compose down -v` borra
todo.

---

## 4. Si tiene que quedar disponible siempre

El túnel sirve para una demo puntual. Para algo permanente, la forma natural de este
proyecto es **un VPS chico con este mismo `docker-compose.prod.yml`** detrás de un proxy
que termine TLS (Caddy resuelve el certificado solo).

Encaja bien porque el proyecto ya es un stack de compose de una sola réplica: no hay nada
que partir. Alcanza con la instancia más chica de cualquier proveedor —el consumo lo
domina MySQL— más un dominio.

Lo que cambia respecto de la demo:

1. El frontend se publica en el puerto del proxy en vez de en loopback.
2. El proxy termina TLS y reenvía al frontend.
3. `CORS_ORIGINS` pasa a ser el dominio real.
4. Hace falta una rutina de backup del volumen de MySQL.

**No escalar el backend a más de una réplica** sin resolver antes un lock distribuido para
el job de recurrentes: cada réplica dispararía el suyo. La UNIQUE `(rule_id, occurred_on)`
evita los duplicados, pero llenaría los logs de `IntegrityError`.
