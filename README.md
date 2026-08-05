# Gestor Inteligente de Finanzas Personales

Aplicación web para administrar finanzas personales: registro de ingresos y gastos,
categorías, presupuestos mensuales, movimientos recurrentes, reportes y un asistente
conversacional que responde consultas en lenguaje natural sobre los movimientos
del usuario.

> **Especificación completa**: [`docs/PROMPT.md`](docs/PROMPT.md). Ese documento es la
> fuente de la verdad del proyecto — alcance, arquitectura, contrato de API, criterios
> de aceptación y decisiones cerradas. Ante duda o conflicto, manda ese archivo.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| ORM / Migraciones | SQLAlchemy 2.0 (async) + Alembic |
| Base de datos | MySQL 8 |
| Scheduler | APScheduler (in-process) |
| IA | LangChain + OpenAI API |
| Auth | JWT (access + refresh) |
| Contenedores | Docker + docker compose |

---

## Puesta en marcha

### Requisitos

- Docker Desktop (con el daemon corriendo)
- Node.js 22+ y npm — solo si querés correr el frontend fuera de Docker
- Python 3.12 — **opcional**; el backend corre en contenedor

### Levantar todo

```bash
cp .env.example .env
# editá .env: al menos JWT_SECRET_KEY y OPENAI_API_KEY
docker compose up --build
```

| Servicio | URL |
|---|---|
| Frontend | http://localhost:8080 |
| API | http://localhost:8000 |
| Documentación OpenAPI | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Generar un `JWT_SECRET_KEY` real:

```bash
docker compose run --rm backend python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Frontend en modo desarrollo (hot reload)

```bash
cd frontend
npm install
npm run dev
```

Queda en http://localhost:5173 y proxea `/api` y `/health` al backend en el puerto 8000.

---

## Comandos

### Backend (dentro del contenedor)

```bash
docker compose exec backend pytest
```

| Acción | Comando |
|---|---|
| Tests completos | `docker compose exec backend pytest` |
| Solo unitarios (sin base) | `docker compose exec backend pytest -m "not integration"` |
| Cobertura | `docker compose exec backend pytest --cov=app --cov-report=term-missing` |
| Lint | `docker compose exec backend ruff check .` |
| Formato | `docker compose exec backend ruff format .` |
| Tipos | `docker compose exec backend mypy app` |
| Nueva migración | `docker compose exec backend alembic revision --autogenerate -m "descripcion"` |
| Aplicar migraciones | `docker compose exec backend alembic upgrade head` |

Los tests corren contra una base **separada** (`finanzas_test`), no contra la de
desarrollo: la suite trunca todas las tablas entre casos. El nombre se deriva
solo, agregándole `_test` al de `DATABASE_URL`, así que no depende de que nadie
se acuerde de setear una variable. La base la crea `db/init/` la primera vez que
se inicializa el volumen de MySQL.

### Frontend

```bash
npm run test:ci
```

| Acción | Comando |
|---|---|
| Dev server | `npm run dev` |
| Tests | `npm run test` (watch) · `npm run test:ci` |
| Cobertura | `npm run test:coverage` |
| Lint | `npm run lint` |
| Tipos | `npm run typecheck` |
| Build | `npm run build` |

---

## Arquitectura

Clean Architecture, dependencias hacia adentro:

```
domain/          entidades, value objects (Money), enums, calendario de recurrencias
   ↑             código puro — no importa FastAPI, SQLAlchemy ni nada externo
application/     casos de uso, puertos (Protocol), DTOs
   ↑             accede a lo externo SOLO por interfaces
infrastructure/  SQLAlchemy, repositorios, cliente OpenAI, agente, scheduler, Clock
   ↑
api/             routers, schemas, dependencias. Sin lógica de negocio.
```

Reglas que el código debe respetar (detalle en `docs/PROMPT.md` §4):

- El job del scheduler no tiene lógica: invoca un caso de uso, igual que un endpoint.
- Los routers validan, delegan y mapean. Nada más.

---

## Decisiones cerradas

| Tema | Decisión | Detalle |
|---|---|---|
| Alcance | 12 casos de uso: movimientos + presupuestos + recurrentes | §17 |
| Moneda | **ARS única en v1**, esquema y dominio preparados para USD | §5.1 |
| Zona horaria | **Fija del servidor**: `America/Argentina/Buenos_Aires`, vía puerto `Clock` | §5.2 |
| Idioma | **Solo español**, locale `es-AR`, sin i18n | §5.3 |
| Modelo de IA | Escalón `mini`, configurable por `OPENAI_MODEL`, con telemetría de tokens | §11 |

Consecuencias operativas de esas decisiones:

- **Nunca sumar montos sin filtrar por moneda**, aunque hoy solo exista ARS.
- **Nunca llamar a `date.today()` fuera del `Clock`**, ni calcular fechas en SQL.
- **La API habla ISO** (fechas `YYYY-MM-DD`, montos `"1234.56"`); el formato `es-AR`
  vive solo en la vista.
- **Los errores traen `code` en inglés estable y `message` en español.** El frontend
  mapea por `code`, nunca por el texto.

---

## Seguridad

- Aislamiento multiusuario: toda consulta filtra por el `user_id` del token. Pedir un
  recurso ajeno devuelve **404**, no 403, para no filtrar su existencia.
- Contraseñas con **Argon2id** (no bcrypt, que trunca en silencio a 72 bytes).
- El login **no distingue** "email inexistente" de "contraseña incorrecta", ni en el
  mensaje ni en el tiempo de respuesta: cuando el email no existe igual se verifica
  contra un hash descartable, para que la diferencia de latencia no permita enumerar
  cuentas.
- Los **refresh tokens rotan**: el usado se revoca al canjearlo, así que reutilizarlo
  falla y es señal de que se filtró. En la base se guarda el SHA-256, nunca el token.
- Un refresh token **no sirve** para autenticar requests, y un access token no sirve
  para renovar: el tipo va en el claim `typ` y se verifica en los dos sentidos.
- El asistente usa **tools con `user_id` cerrado**, no SQL libre: una prompt injection
  no puede leer datos de otro usuario porque el `user_id` no es un parámetro que el
  modelo pueda elegir.
- **Almacenamiento de la sesión en el navegador**: el *access token* vive **solo en
  memoria** y el *refresh token* en `localStorage`. Lo ideal sería una cookie
  `httpOnly`, pero el backend devuelve los tokens en el cuerpo de la respuesta y
  cambiar eso implicaría además resolver CSRF.
  **El trade-off que queda**: un XSS puede leer el refresh token de `localStorage`.
  Se mitiga en parte porque el refresh **rota** —usarlo lo revoca, así que el robo se
  vuelve detectable y la ventana se acota— y porque el access token, que es el que
  abre todos los endpoints, nunca se persiste: cerrar la pestaña lo borra. Migrar a
  cookies `httpOnly` queda como mejora pendiente.
- La API key de OpenAI vive solo en el backend, por variable de entorno.
- Nunca se loguean tokens, contraseñas, prompts del usuario ni montos junto a un email.
- `.env` está en `.gitignore`. En el repo solo hay `.env.example` con valores dummy.

---

## Estado del proyecto

Plan de 14 fases (detalle en `docs/PROMPT.md` §18).

- [x] **Fase 1 — Scaffolding**: estructura, docker compose, `.env.example`, health check, CI
- [x] **Fase 2 — Dominio y persistencia**: `Money`, `Clock`, entidades, modelos, mappers, migración inicial
- [x] **Fase 3 — Autenticación**: registro, login, refresh con rotación, logout, `get_current_user`, seed de categorías
- [x] **Fase 4 — Categorías**: ABM completo, unicidad por usuario y tipo, borrado bloqueado con detalle
- [x] **Fase 5 — Transacciones**: CRUD, filtros combinables, orden validado y paginación estable
- [x] **Fase 6 — Reportes y export CSV**: resumen, agregado por categoría, tendencia mensual sin agujeros y export con formato para Excel
- [x] **Fase 7 — Presupuestos (backend)**: ABM, progreso con estados, copia entre meses
- [x] **Fase 8 — Frontend base**: routing con guards, cliente HTTP con refresh, formateo es-AR, login y registro
- [x] **Fase 9 — Frontend features**: dashboard con gráficos, movimientos con filtros, ABM de categorías, presupuestos y reportes
- [ ] Fase 10 — Asistente LangChain
- [ ] Fase 11 — Frontend chat
- [ ] Fase 12 — Recurrentes (backend)
- [ ] Fase 13 — Frontend recurrentes
- [ ] Fase 14 — Cierre

---

## Servidores MCP usados

| Servidor | Uso |
|---|---|
| **Filesystem MCP** | Lectura y escritura de los archivos del proyecto |
| **GitHub MCP** | Gestión del repositorio, ramas, pull requests e issues |

La configuración va en el cliente MCP correspondiente. **No incluyas tokens reales
en el repositorio**: el token de GitHub se pasa por variable de entorno.

---

## Notas operativas

### Scheduler y réplicas

El job de movimientos recurrentes corre in-process con APScheduler. La idempotencia
está garantizada por la constraint `UNIQUE (rule_id, occurred_on)` de
`recurring_occurrences`, así que **con una sola réplica del backend alcanza**.

Si en algún momento se escala a varias réplicas, hace falta un lock distribuido: sin
eso, cada réplica dispararía su propio job. La UNIQUE evitaría los duplicados, pero
generaría ruido de `IntegrityError` en los logs.

### Consumo de tokens del asistente

Desde la fase 10, cada consulta al chat deja una fila en `chat_usage`. Para revisar el
consumo real:

```sql
SELECT
    DATE(created_at)                     AS dia,
    COUNT(*)                             AS consultas,
    ROUND(AVG(prompt_tokens))            AS prompt_prom,
    ROUND(AVG(completion_tokens))        AS completion_prom,
    ROUND(AVG(total_tokens))             AS total_prom,
    ROUND(AVG(tool_calls_count), 2)      AS tools_prom,
    ROUND(AVG(latency_ms))               AS latencia_ms_prom
FROM chat_usage
GROUP BY DATE(created_at)
ORDER BY dia DESC;
```

**Revisar a la semana de uso real** y recalibrar `OPENAI_MODEL`, `OPENAI_MAX_TOKENS` y
`CHAT_HISTORY_WINDOW` con esos datos en vez de con estimaciones.

### Roadmap: habilitar USD

El esquema ya tiene la columna `currency` en `transactions`, `budgets` y
`recurring_rules`, y el dominio usa el value object `Money`, que rechaza operaciones
entre monedas distintas. Habilitar USD implica:

1. `SUPPORTED_CURRENCIES=ARS,USD`
2. Selector de moneda en el frontend
3. Responder la pregunta de producto que queda abierta:
   **¿el tipo de cambio se congela al momento de la operación, o se aplica el vigente
   al momento de consultar?** De eso depende si hace falta persistir la cotización en
   cada movimiento.

No hay conversión ni cotizaciones implementadas, y no debe agregarse sin cerrar ese punto.

---

## Convenciones

- **Conventional Commits**: `<type>[scope]: <descripción en imperativo>`
  (`feat`, `fix`, `test`, `chore`, `docs`, `style`, `refactor`, `perf`, `build`, `ci`, `revert`).
- Trunk-based: ramas de vida corta desde `main`, PR obligatorio, squash merge.
- El PR no se mergea con el pipeline en rojo.
