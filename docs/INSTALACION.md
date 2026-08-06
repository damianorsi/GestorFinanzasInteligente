# Guía de instalación

Cómo levantar el proyecto completo para probarlo, de cero, en una máquina nueva.

> El camino corto: instalar Docker, copiar `.env.example` a `.env`, generar una clave JWT
> y correr `docker compose up --build`. Los detalles y lo que suele fallar están abajo.

---

## 1. Qué hace falta instalar

### Obligatorio

| Herramienta | Versión | Para qué | Cómo verificar |
|---|---|---|---|
| **Docker Engine** | 20.10 o superior | Corre los tres servicios | `docker --version` |
| **Docker Compose** | **v2** — el plugin `docker compose`, no el viejo `docker-compose` | Orquesta el stack | `docker compose version` |
| **Git** | cualquiera reciente | Clonar el repositorio | `git --version` |

El requisito real es **Compose v2**: el `docker-compose.yml` usa la clave `name` de nivel
superior y `depends_on` con `condition: service_healthy`, que el binario viejo no entiende.
Verificado sobre Docker Engine 29.4.2 y Compose v5.1.3.

En Windows y macOS alcanza con **Docker Desktop**, que trae el engine y el plugin de
compose. En Linux hace falta `docker-ce` más `docker-compose-plugin`.

**No hace falta instalar Python, MySQL ni Node** para levantar y probar la aplicación:
los tres corren dentro de contenedores.

### Opcional — solo para desarrollar

| Herramienta | Versión | Para qué |
|---|---|---|
| **Node.js** | 22 o superior | Correr el frontend con hot reload y su suite de tests fuera de Docker |
| **npm** | el que viene con Node | Ídem |

El backend **siempre** se trabaja dentro del contenedor (`docker compose exec backend …`),
así que Python local no es necesario ni siquiera para desarrollar.

### Versiones que usa el proyecto por dentro

Esto es informativo: las fija el `Dockerfile` y no hay que instalarlas a mano.

| Componente | Versión |
|---|---|
| Python | 3.12 (`python:3.12-slim`) |
| MySQL | 8.0 (`mysql:8.0`) |
| Node (build del frontend) | 22 (`node:22-alpine`) |
| nginx (sirve el frontend) | 1.27 (`nginx:1.27-alpine`) |
| FastAPI · SQLAlchemy · Alembic | 0.115+ · 2.0.36+ · 1.14+ |
| React · Vite · TypeScript | 18 · 6 · 5.7 |
| LangChain · langchain-openai | 1.x (`>=1.3,<2`) · 1.x (`>=1.4,<2`) |
| APScheduler | 3.11+ (`<4`) |

> El major de LangChain está acotado a propósito: el agente usa `create_agent`, que es de
> la 1.x. La 0.3 exponía `AgentExecutor`, que ya no existe, así que un rango más laxo
> dejaría instalar una versión donde la aplicación no arranca.

---

## 2. Levantar el proyecto

```bash
git clone git@github.com:damianorsi/GestorFinanzasInteligente.git
cd GestorFinanzasInteligente
```

### Paso 1 — crear el `.env`

```bash
cp .env.example .env
```

En Windows con PowerShell:

```powershell
Copy-Item .env.example .env
```

**El archivo `.env` es obligatorio.** Sin él, compose ni siquiera intenta levantar:

```
error while interpolating services.db.environment.MYSQL_PASSWORD:
required variable MYSQL_PASSWORD is missing a value: definir en .env
```

### Paso 2 — generar una clave JWT real

El valor de ejemplo sirve para desarrollo, pero la aplicación **se niega a arrancar con él
si `APP_ENV=production`**. Conviene generar uno propio desde el principio:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pegá el resultado en `JWT_SECRET_KEY` dentro de `.env`.

### Paso 3 — levantar todo

```bash
docker compose up --build
```

La primera vez tarda varios minutos: construye las imágenes, inicializa MySQL y corre las
migraciones. Cuando termina, en los logs se ve `Scheduler iniciado` y el health del
backend en verde.

| Servicio | URL |
|---|---|
| Aplicación | http://localhost:8080 |
| API | http://localhost:8000 |
| Documentación interactiva (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Para dejarlo corriendo en segundo plano: `docker compose up --build -d`.

### Paso 4 — verificar que quedó bien

```bash
curl http://localhost:8000/health
```

En PowerShell, `curl` es un alias de `Invoke-WebRequest` y muestra otra cosa. Usá:

```powershell
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json
```

Tiene que devolver algo así:

```json
{
  "status": "ok",
  "environment": "development",
  "timezone": "America/Argentina/Buenos_Aires",
  "default_currency": "ARS",
  "database": "ok",
  "scheduler": "pending",
  "scheduler_last_run": null
}
```

- `database: "ok"` significa que MySQL responde y las migraciones corrieron.
- `scheduler: "pending"` es lo esperado: el job de recurrentes arrancó y todavía no le tocó
  correr. Pasa a `"ok"` después de la primera corrida (03:00 por defecto).

---

## 3. Qué configurar en `.env`

### Lo que hay que cambiar sí o sí

| Variable | Por qué |
|---|---|
| `JWT_SECRET_KEY` | Firma los tokens de sesión. Con el valor de ejemplo, cualquiera que conozca el repositorio puede falsificar un token. |

### Lo que hay que cambiar para que el asistente funcione

| Variable | Por qué |
|---|---|
| `OPENAI_API_KEY` | Sin una clave real, el chat responde siempre con `degraded: true` y un mensaje de fallback. **El resto de la aplicación funciona igual.** Se saca de https://platform.openai.com/api-keys |
| `OPENAI_MODEL` | Viene en `gpt-5-mini`. Verificá el identificador exacto y el precio vigente en https://platform.openai.com/pricing antes de fijarlo. |

La clave de OpenAI vive **solo en el backend**, por variable de entorno. Nunca va en el
frontend ni se commitea.

### Lo que conviene cambiar antes de exponer la aplicación

| Variable | Valor de ejemplo | Comentario |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `cambiame_root` | Contraseña de root de MySQL |
| `MYSQL_PASSWORD` | `cambiame_app` | Contraseña de la aplicación. Si la cambiás, actualizá también `DATABASE_URL`, que la lleva embebida |
| `APP_ENV` | `development` | En `production` la aplicación valida que los secretos y los parámetros de Argon2 no sean los de ejemplo |
| `CORS_ORIGINS` | `localhost:5173,localhost:8080` | Orígenes permitidos |

### Lo que podés dejar como está

Puertos (`BACKEND_PORT`, `FRONTEND_PORT`, `MYSQL_PORT`), zona horaria, moneda, guardrails
del asistente (`AGENT_MAX_ITERATIONS`, `CHAT_HISTORY_WINDOW`, `CHAT_RATE_LIMIT_PER_HOUR`),
parámetros de Argon2 y del job de recurrentes.

Si algún puerto está ocupado en tu máquina —**3306 es el caso típico, con un MySQL local
ya instalado**— cambiá el valor en `.env` y volvé a levantar:

```
MYSQL_PORT=3307
```

---

## 4. Probar la aplicación

Entrá a http://localhost:8080 y registrate con cualquier email. El registro **siembra
categorías por defecto**, así que se puede cargar un movimiento enseguida.

Un recorrido que toca casi todo:

1. **Movimientos** → cargá un ingreso y un gasto.
2. **Resumen** → las tarjetas y los gráficos ya reflejan lo cargado.
3. **Presupuestos** → definí un tope para la categoría del gasto y mirá la barra de avance.
4. **Recurrentes** → creá una regla mensual. La tarjeta muestra las próximas tres fechas
   que va a generar. Probá con día 31 para ver el ajuste en los meses cortos.
5. **Reportes** → cambiá el período y exportá el CSV.
6. **Asistente** → preguntale "¿cuánto gasté este mes?". Sin `OPENAI_API_KEY` real vas a
   recibir el mensaje de fallback; con una clave cargada, responde con tus datos.

### Sobre los movimientos recurrentes

Las reglas **no generan movimientos al instante**: los crea un job que corre una vez por
día —a las 03:00 por defecto— y **nunca materializa fechas futuras**. Recién creada una
regla, es normal que el historial esté vacío. Para disparar una corrida sin esperar:

```bash
docker compose exec backend python -m app.infrastructure.scheduler
```

```
Job ejecutado. Movimientos generados: 2
```

Es idempotente: se puede correr las veces que haga falta sin duplicar nada.

---

## 5. Modo desarrollo

### Backend

El código está montado como volumen y uvicorn recarga solo: editás y el cambio se aplica.
Todos los comandos van dentro del contenedor.

| Acción | Comando |
|---|---|
| Tests | `docker compose exec backend pytest` |
| Solo unitarios (sin base) | `docker compose exec backend pytest -m "not integration"` |
| Cobertura | `docker compose exec backend pytest --cov=app --cov-report=term-missing` |
| Lint | `docker compose exec backend ruff check .` |
| Formato | `docker compose exec backend ruff format .` |
| Tipos | `docker compose exec backend mypy app` |
| Nueva migración | `docker compose exec backend alembic revision --autogenerate -m "descripcion"` |

Los tests corren contra `finanzas_test`, una base **separada** que se crea sola la primera
vez que se inicializa el volumen de MySQL. La suite borra todas las tablas entre casos, así
que no puede correr contra la base de desarrollo.

> Si tocás `backend/pyproject.toml` para agregar una dependencia, hace falta
> `docker compose build backend` — el código está montado, pero las librerías instaladas
> viven en la imagen.

### Frontend

El contenedor sirve el build de producción. Para trabajar con hot reload conviene correrlo
fuera de Docker, contra el backend del contenedor:

```bash
cd frontend
npm install
npm run dev
```

Queda en http://localhost:5173 y proxea `/api` y `/health` al backend en el 8000.

| Acción | Comando |
|---|---|
| Tests | `npm run test` (watch) · `npm run test:ci` |
| Cobertura | `npm run test:coverage` |
| Lint | `npm run lint` |
| Tipos | `npm run typecheck` |
| Build | `npm run build` |

---

## 6. Problemas frecuentes

**`required variable MYSQL_PASSWORD is missing a value: definir en .env`**
Falta el archivo `.env`. Copiá `.env.example`.

**`bind: address already in use` al levantar**
Otro proceso ocupa el puerto. El caso típico es un MySQL instalado en la máquina tomando
el 3306. Cambiá `MYSQL_PORT`, `BACKEND_PORT` o `FRONTEND_PORT` en `.env`.

**El backend queda reiniciándose**
Mirá `docker compose logs backend`. Las dos causas habituales son que MySQL todavía no
terminó de inicializar —la primera vez tarda— o que `DATABASE_URL` no coincide con
`MYSQL_USER` y `MYSQL_PASSWORD`.

**El asistente siempre responde "No pude consultar tus datos en este momento"**
Es el mensaje de fallback: falta una `OPENAI_API_KEY` real en `.env`. Después de cargarla,
reiniciá el backend con `docker compose restart backend`.

**Los tests fallan con `Unknown database 'finanzas_test'`**
El script que crea esa base corre **una sola vez**, cuando el volumen de MySQL se
inicializa vacío. Si el volumen se creó antes de que existiera el script, hay que
recrearlo (ver la sección siguiente) o crear la base a mano.

**Una regla recurrente no genera nada**
Es el comportamiento esperado si sus fechas todavía no llegaron: el job nunca materializa
el futuro. Verificá `next_dates` en la tarjeta de la regla y, si querés adelantar la
corrida, usá `docker compose exec backend python -m app.infrastructure.scheduler`.

**Reactivé una regla pausada y no generó los meses de la pausa**
Es a propósito. Pausar es decidir no generar, no diferir: al reactivar, las fechas del
período pausado quedan anotadas como salteadas. Si no fuera así, reactivar una regla
pausada tres meses inyectaría de golpe tres meses de movimientos que nunca ocurrieron.

---

## 7. Empezar de cero

Borra **todos los datos**, incluida la base:

```bash
docker compose down -v
docker compose up --build
```

Sin `-v` el volumen sobrevive y los datos quedan.

---

## 8. Documentación relacionada

- [`docs/DESPLIEGUE.md`](DESPLIEGUE.md) — cómo exponer la aplicación para que otras
  personas la prueben. **El `docker-compose.yml` de este documento no se expone**: publica
  MySQL en el host.
- [`README.md`](../README.md) — arquitectura, decisiones cerradas, seguridad y notas
  operativas (scheduler, consumo de tokens, roadmap de USD).
- [`docs/PROMPT.md`](PROMPT.md) — especificación completa del proyecto. Ante duda o
  conflicto, manda ese archivo.
- http://localhost:8000/docs — contrato de la API, navegable, con el stack levantado.
