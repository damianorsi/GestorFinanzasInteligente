# PROMPT — Gestor Inteligente de Finanzas Personales

## 1. Rol y objetivo

Actuá como arquitecto y desarrollador full-stack senior. Tu tarea es **diseñar e implementar desde cero** una aplicación web de gestión de finanzas personales con un asistente conversacional basado en IA.

Trabajá de forma incremental y verificable: **cada fase termina con código que compila, tests que pasan y un commit**. No avances a la fase siguiente si la anterior no está verde. No inventes APIs, paquetes ni versiones: si algo no está definido acá, preguntá o dejá un `TODO` explícito con la duda.

**Todas las decisiones de alcance están cerradas** (ver §5 y §19). No vuelvas a preguntar por moneda, zona horaria, idioma, alcance de casos de uso ni modelo de IA.

## 2. Producto

Aplicación web donde un usuario registra ingresos y gastos, los clasifica por categorías, define **presupuestos mensuales** por categoría, automatiza sus movimientos fijos mediante **reglas recurrentes**, visualiza estadísticas y consulta sus finanzas en lenguaje natural mediante un chatbot. El objetivo del producto es **facilitar la organización financiera y dar recomendaciones accionables** sobre la administración del dinero.

## 3. Stack tecnológico (obligatorio)

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| ORM / Migraciones | SQLAlchemy 2.0 (estilo declarativo tipado) + Alembic |
| Base de datos | MySQL 8 |
| Scheduler | APScheduler (in-process, arrancado en el lifespan de FastAPI) |
| IA | LangChain + OpenAI API |
| Autenticación | JWT (access + refresh) |
| Contenedores | Docker + docker compose |
| Control de versiones | Git + GitHub |
| Testing back | pytest + pytest-asyncio + httpx.AsyncClient + freezegun |
| Testing front | Vitest + @testing-library/react + MSW |

Complementos permitidos (usalos, no reimplementes): `passlib[bcrypt]` o `argon2-cffi` para hashing, `python-jose` o `PyJWT` para tokens, `pydantic-settings` para configuración, `python-dateutil` para aritmética de calendario, `Recharts` para gráficos, `Redux Toolkit` o `TanStack Query` para estado remoto, `react-router-dom v6`, `slowapi` para rate limiting.

**No agregues dependencias fuera de esta lista sin justificarlo en el PR.** En particular: **no instales ninguna librería de i18n** (ver §5.3).

## 4. Arquitectura

Clean Architecture con dependencias hacia adentro. Estructura de repositorio:

```
/
├── backend/
│   ├── app/
│   │   ├── domain/            # entidades, value objects (Money), enums, excepciones, calendario. Cero imports de FastAPI/SQLAlchemy
│   │   ├── application/       # casos de uso (un archivo por caso de uso), puertos (Protocol), DTOs
│   │   ├── infrastructure/    # SQLAlchemy models, repositorios, sesión DB, cliente OpenAI, agente LangChain, scheduler, clock
│   │   ├── api/
│   │   │   ├── v1/routers/    # endpoints, versionados
│   │   │   ├── deps.py        # inyección de dependencias (get_db, get_current_user, get_clock)
│   │   │   └── schemas/       # request/response Pydantic
│   │   ├── core/              # config, seguridad, logging, manejo de errores
│   │   └── main.py
│   ├── alembic/
│   ├── tests/{unit,integration}/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/{components,pages,features,services,hooks,store,types,routes,styles,utils,__tests__}/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
└── .github/workflows/ci.yml
```

Reglas de capas, no negociables:
- `domain/` no importa nada de `application/`, `infrastructure/` ni `api/`. **El value object `Money` y la aritmética de calendario viven acá, como código puro testeable sin DB.**
- `application/` accede a la DB, a OpenAI, al reloj y a cualquier recurso externo **solo a través de interfaces** (`typing.Protocol`) implementadas en `infrastructure/`.
- Los routers de `api/` no contienen lógica de negocio: validan, delegan al caso de uso y mapean la respuesta.
- **El job del scheduler no contiene lógica**: invoca un caso de uso de `application/`, igual que un endpoint. Debe poder ejecutarse desde un test sin levantar el scheduler.
- Separación tipo CQRS liviano: casos de uso de escritura (`commands/`) validan reglas de negocio; los de lectura (`queries/`) devuelven DTOs sin lógica.

---

## 5. Moneda, zona horaria e idioma

Las tres decisiones están **cerradas**. Esta sección es normativa: se aplica a todas las capas.

### 5.1 Moneda — ARS en v1, preparado para USD

**En v1 el sistema opera exclusivamente en pesos argentinos (ARS).** No hay selector de moneda, ni conversión, ni cotizaciones.

**Pero el diseño debe admitir USD sin migración destructiva ni refactor.** Concretamente, implementá desde el día uno:

**a) Columna `currency` en las tres tablas con montos**

`transactions`, `budgets` y `recurring_rules` llevan `currency CHAR(3) NOT NULL DEFAULT 'ARS'` desde la primera migración. Habilitar USD después no toca el esquema.

Las categorías **no** llevan moneda: una categoría "Alimentación" sirve para gastos en cualquier moneda.

**b) Value object `Money` en `domain/`**

**Esta es la decisión que hace barato el cambio futuro.** No pasees `Decimal` pelado por los casos de uso: si lo hacés, sumar moneda después obliga a tocar cada uno.

```python
@dataclass(frozen=True)
class Money:
    amount: Decimal      # siempre positivo, 2 decimales
    currency: str        # ISO 4217, 'ARS' en v1
```

Reglas del VO, con tests propios:
- Inmutable.
- Rechaza más de 2 decimales, valores no finitos y **la construcción desde `float`**.
- **Admite valores negativos.** La regla "los montos son siempre positivos" es una invariante de las *entidades* `Transaction`, `Budget` y `RecurringRule` —donde el signo lo determina el `TransactionType`—, no del tipo en sí: un balance es una resta y puede dar negativo. Ponerle esa restricción al value object obligaría a devolver los balances como `Decimal` pelado, que es exactamente lo que este tipo viene a evitar.
- **Sumar, restar o comparar dos `Money` de distinta moneda lanza `CurrencyMismatchError`.** Nunca hace conversión implícita. Esta guarda es la que garantiza que el día que entre USD, cualquier mezcla accidental explote en un test en vez de producir un balance silenciosamente incorrecto. La *igualdad* entre monedas distintas devuelve `False` en vez de lanzar: preguntar si dos montos son iguales es legítimo, ordenarlos no.

**c) La moneda es una dimensión de filtrado, no un cambio de forma en la respuesta**

Toda agregación (resúmenes, reportes, progreso de presupuestos, tools del chat) filtra explícitamente por moneda: `WHERE currency = :currency`, con `:currency` = `DEFAULT_CURRENCY` en v1. **Nunca sumes montos sin filtrar por moneda, aunque hoy solo haya una.**

Todos los endpoints de lectura con montos aceptan un query param opcional `currency`, con default `ARS`, validado contra `SUPPORTED_CURRENCIES`. En v1 mandar `?currency=USD` devuelve **422** (`unsupported_currency`).

Toda respuesta que contenga montos incluye un campo `currency` explícito. **Nunca devuelvas un monto sin su moneda al lado.**

Motivo del diseño: cuando entre USD, el producto va a mostrar las finanzas **por moneda separada** (un selector), no un balance mezclado — porque mezclar exige una fuente de cotización y una política de "¿qué tipo de cambio, el del día de la operación o el de hoy?", que es una decisión de producto que no corresponde tomar ahora. Con la moneda como filtro, la forma de las respuestas ya es la definitiva y no se rompe nada.

**d) Presupuestos por moneda**

La UNIQUE de `budgets` es `(user_id, category_id, period_month, currency)`. Un presupuesto de $200.000 en Alimentación y otro de US$100 en la misma categoría son dos filas válidas.

**e) Formateo centralizado en el front**

Un único helper `formatMoney(amount: string, currency: string)` en `utils/`, implementado con `Intl.NumberFormat('es-AR', { style: 'currency', currency })`. **Prohibido formatear montos inline en los componentes.** El día que entre USD, se toca una función.

**f) Configuración**

`DEFAULT_CURRENCY=ARS` y `SUPPORTED_CURRENCIES=ARS` como variables de entorno. Habilitar USD debe ser, idealmente, pasar `SUPPORTED_CURRENCIES=ARS,USD` y agregar el selector en el front.

**g) Explícitamente FUERA de alcance en v1** — no lo implementes:

- Tipos de cambio, conversión y cotizaciones.
- Totales o balances que mezclen monedas.
- Selector de moneda en la UI.
- Reglas recurrentes o presupuestos en moneda distinta de ARS.

Dejá esto documentado en el README como roadmap, junto con la pregunta abierta que habrá que responder entonces: **¿el tipo de cambio se congela al momento de la operación o se aplica el vigente al consultar?**

### 5.2 Zona horaria — fija del servidor

- Zona única para toda la aplicación: **`America/Argentina/Buenos_Aires`**, en `APP_TIMEZONE`. Los contenedores de backend y de MySQL arrancan con `TZ` seteado a ese valor.
- **Fechas de negocio** (`occurred_on`, `period_month`, `starts_on`, `ends_on`) son `DATE` **sin hora**. Al no tener hora, no tienen ambigüedad de zona horaria: ese es el punto de la decisión.
- **Timestamps de auditoría** (`created_at`, `updated_at`) se almacenan en **UTC** y se convierten a `APP_TIMEZONE` recién en la capa de presentación.
- **Puerto `Clock` obligatorio.** Definí una interfaz `Clock` con `today() -> date` y `now() -> datetime`, implementada en `infrastructure/` resolviendo sobre `APP_TIMEZONE`, e inyectada en todos los casos de uso que la necesiten.

  **Prohibido llamar a `date.today()` o `datetime.now()` desperdigados por el código.** Motivo: el job de recurrentes y la resolución de fechas relativas del chatbot ("este mes") dependen de qué día es "hoy"; con un `Clock` inyectable, `freezegun` controla el tiempo en los tests de forma confiable y la decisión de zona horaria queda aplicada en un solo lugar.

- **Prohibido calcular fechas en SQL** (`CURDATE()`, `NOW()`, `DATE_SUB()` sobre "hoy"). Las fechas se calculan en Python con el `Clock` y se pasan como parámetro a la query. Esto elimina de raíz que la zona horaria de la sesión de MySQL discrepe con la del backend.
- El job de recurrentes corre a `RECURRING_JOB_HOUR` (default 03:00) en `APP_TIMEZONE`.
- Consecuencia de producto a documentar en el README: **es un producto de zona horaria única.** Un usuario viajando por Europa carga movimientos con fecha de Argentina. Es aceptable y es la decisión tomada.

### 5.3 Idioma — solo español

- **UI exclusivamente en español rioplatense.** Sin i18n, sin librería de internacionalización, sin archivos de traducción. Los textos van directo en los componentes.
- Locale de formateo: **`es-AR`** — separador decimal coma, separador de miles punto, fechas `dd/MM/yyyy`. Centralizado en `utils/` junto a `formatMoney`, nunca inline.
- **Separación crítica entre transporte y presentación**: la API siempre habla ISO — fechas `YYYY-MM-DD`, montos como string con punto decimal (`"1234.56"`). La localización ocurre **solo en la capa de vista del front**. Nunca mandes un monto formateado ni una fecha `dd/MM/yyyy` por el JSON.
- **Mensajes de error bilingües por diseño**: el campo `message` va en español (lo lee el usuario), pero el campo `code` va en **inglés, snake_case y estable** (`unsupported_currency`, `category_has_transactions`, `budget_already_exists`). El front mapea por `code`, nunca por el texto del mensaje.
- El system prompt y las respuestas del asistente, en español rioplatense neutro.
- Costo asumido y documentado: agregar otro idioma más adelante exige extraer los strings de los componentes. Es una decisión consciente, no un descuido.

---

## 6. Modelo de datos

Tablas (MySQL 8, InnoDB, `utf8mb4`):

- **users**: `id` (BIGINT PK), `email` (UNIQUE, NOT NULL), `password_hash`, `full_name`, `is_active`, `created_at`, `updated_at`.
- **categories**: `id`, `user_id` (FK → users, ON DELETE CASCADE), `name`, `type` (ENUM `INCOME`/`EXPENSE`), `color`, `is_default`, `created_at`, `updated_at`. UNIQUE `(user_id, name, type)`. *(Sin moneda: es transversal.)*
- **transactions**: `id`, `user_id` (FK), `category_id` (FK → categories, ON DELETE RESTRICT), `type` (ENUM `INCOME`/`EXPENSE`), `amount` **DECIMAL(14,2)**, **`currency` CHAR(3) NOT NULL DEFAULT 'ARS'**, `occurred_on` (DATE), `description` (VARCHAR 255), `recurring_rule_id` (FK → recurring_rules, **NULLABLE**, ON DELETE SET NULL), `created_at`, `updated_at`. Índices: `(user_id, occurred_on)`, `(user_id, category_id)`, `(user_id, type)`, **`(user_id, currency, occurred_on)`**.
- **budgets**: `id`, `user_id` (FK), `category_id` (FK → categories, ON DELETE CASCADE), `period_month` (DATE, siempre día 1 del mes), `amount` DECIMAL(14,2), **`currency` CHAR(3) NOT NULL DEFAULT 'ARS'**, `created_at`, `updated_at`. UNIQUE **`(user_id, category_id, period_month, currency)`**. Índice `(user_id, period_month)`.
- **recurring_rules**: `id`, `user_id` (FK), `category_id` (FK), `type` (ENUM), `amount` DECIMAL(14,2), **`currency` CHAR(3) NOT NULL DEFAULT 'ARS'**, `description`, `frequency` (ENUM `DAILY`/`WEEKLY`/`MONTHLY`/`YEARLY`), `day_of_month` (TINYINT, nullable), `day_of_week` (TINYINT, nullable), `starts_on` (DATE), `ends_on` (DATE, nullable), `is_active` (BOOL), `created_at`, `updated_at`. Índice `(user_id, is_active)`.
- **recurring_occurrences** *(libro mayor de idempotencia)*: `id`, `rule_id` (FK → recurring_rules, ON DELETE CASCADE), `occurred_on` (DATE), `status` (ENUM `GENERATED`/`SKIPPED`), `transaction_id` (FK → transactions, nullable, ON DELETE SET NULL), `created_at`. **UNIQUE `(rule_id, occurred_on)`** ← garantía de idempotencia, obligatoria.
- **chat_messages**: `id`, `user_id` (FK), `conversation_id` (UUID), `role` (ENUM `USER`/`ASSISTANT`), `content` (TEXT), `created_at`. Índice `(user_id, conversation_id, created_at)`.
- **chat_usage** *(telemetría de tokens)*: `id`, `user_id` (FK), `conversation_id`, `model`, `prompt_tokens` (INT), `completion_tokens` (INT), `total_tokens` (INT), `tool_calls_count` (INT), `latency_ms` (INT), `created_at`. Índice `(user_id, created_at)`.
- **refresh_tokens** (o denylist de JTI): `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`.

Reglas de datos:
- **El dinero se maneja con `Money` / `Decimal` / `DECIMAL(14,2)` en todas las capas. Nunca `float`.** El JSON serializa montos como string.
- Montos siempre positivos; el signo lo determina `type`.
- **`currency` se valida contra `SUPPORTED_CURRENCIES` en la capa de aplicación**; valor no soportado → 422 `unsupported_currency`.
- **Los presupuestos solo aplican a categorías de tipo `EXPENSE`.** Presupuestar una categoría `INCOME` → 422.
- Reglas recurrentes, presupuestos y movimientos deben referenciar categorías **del mismo usuario**. Validar siempre.
- Al crear un usuario, sembrar categorías por defecto (`is_default=true`): Sueldo, Freelance, Otros ingresos / Alimentación, Transporte, Vivienda, Salud, Ocio, Servicios, Otros gastos.
- Toda migración de esquema va por Alembic. Nada de `create_all()` en producción.

## 7. API REST

Base: `/api/v1`. Recursos en plural, sustantivos, sin verbos.

```
POST   /auth/register            201 → crea usuario + categorías por defecto
POST   /auth/login               200 → { access_token, refresh_token, token_type }
POST   /auth/refresh             200
POST   /auth/logout              204 (revoca refresh token)
GET    /users/me                 200

GET    /categories               200 lista plana, SIN paginar (filtro: type)
GET    /categories/{id}          200 | 404
POST   /categories               201 + header Location
PATCH  /categories/{id}          200 (solo name y color: el tipo es inmutable)
DELETE /categories/{id}          204 | 409 si tiene movimientos, presupuestos o reglas

GET    /transactions             200 (paginado + filtros)
POST   /transactions             201 + header Location
GET    /transactions/{id}        200
PATCH  /transactions/{id}        200
DELETE /transactions/{id}        204

GET    /budgets                  200 (filtros: period_month, currency)
POST   /budgets                  201 | 409 si ya existe para esa categoría, período y moneda
PATCH  /budgets/{id}             200
DELETE /budgets/{id}             204
GET    /budgets/progress         200 (presupuestado vs gastado por categoría del período)
POST   /budgets/copy-from        201 (copia los presupuestos de un período a otro)

GET    /recurring-rules          200 (filtro: is_active)
POST   /recurring-rules          201 + header Location
PATCH  /recurring-rules/{id}     200 (incluye pausar/reactivar vía is_active)
DELETE /recurring-rules/{id}     204 (NO borra los movimientos ya generados)
GET    /recurring-rules/{id}/occurrences  200 (historial generadas/salteadas)
GET    /recurring-rules/upcoming 200 (próximos vencimientos proyectados, al vuelo)

GET    /reports/summary          200 (ingresos, gastos, balance del período)
GET    /reports/by-category      200 (agregado por categoría)
GET    /reports/monthly-trend    200 (serie mensual ingresos vs gastos)

GET    /transactions/export      200 text/csv (mismos filtros que el listado; `format=standard|excel_es`)

POST   /chat                     200 (consulta al asistente)
GET    /chat/history             200
```

- **Todos los endpoints de lectura con montos aceptan `currency` (opcional, default `ARS`) y devuelven el campo `currency` en la respuesta.**
- Filtros de `/transactions`: `date_from`, `date_to`, `category_id`, `type`, `currency`, `min_amount`, `max_amount`, `q` (busca en descripción), `is_recurring` (bool), `sort` (ej. `-occurred_on,amount`).
- **Paginación offset-based**: request `offset` (default 0) + `limit` (default 20, máx 100); response `{ entries: [], offset, limit, totalCount }`. Aplica a `/transactions`, que es la única colección que crece sin techo.
- **`/categories` es la excepción y devuelve un array plano.** La colección está acotada por usuario (arranca en 10 y realistamente no pasa de unas decenas) y el frontend la necesita entera para poblar los selectores de alta de movimiento. Paginarla obligaría a iterar para armar un `<select>`, o —peor— a truncarlo en silencio.
- **El `type` de una categoría es inmutable.** Pasar una de gasto a ingreso convertiría todos sus movimientos históricos en lo contrario de lo que se registró, y ni el balance ni los reportes tendrían forma de detectarlo. Para cambiar de tipo hay que crear otra categoría y mover los movimientos.
- Los schemas de request llevan `extra="forbid"`: un campo desconocido devuelve 422 en vez de ignorarse. Sin eso, mandar `type` en un PATCH de categoría parecería funcionar y no cambiaría nada.
- **El export acepta dos formatos.** `standard` (default) usa coma como separador y punto decimal: es RFC 4180 y lo lee cualquier parser. `excel_es` usa punto y coma y coma decimal, que es lo que Excel en español espera al abrir el archivo con doble clic; con el formato estándar mostraría todo en una sola columna. Van juntos en un solo parámetro y no como dos opciones sueltas porque elegir uno sin el otro produce un archivo roto: con `;` y punto decimal Excel parte la columna del monto.
- El export **no** se pagina, pero tiene tope (`EXPORT_MAX_ROWS`, default 50 000): al superarlo devuelve 422 `export_too_large` pidiendo acotar el filtro. Se avisa en vez de truncar porque un CSV recortado en silencio parece completo.
- Los reportes sin período explícito usan **el mes en curso**, resuelto con el `Clock` en `APP_TIMEZONE`. Un período sin movimientos devuelve ceros y listas vacías, nunca un error.
- `/reports/monthly-trend` **rellena con ceros los meses sin movimientos**: un `GROUP BY` solo devuelve los meses que tienen filas y el gráfico quedaría con agujeros donde en realidad hubo actividad nula.
- El porcentaje de `/reports/by-category` lo calcula el backend, **por tipo por separado**: mezclar ingresos y gastos en un mismo 100% no significaría nada, y calcularlo en el frontend haría que cada consumidor pudiera redondear distinto.
- Fechas en ISO `YYYY-MM-DD`; montos como string con punto decimal. **Nunca formato localizado en el JSON.**
- Códigos de estado: 200, 201 (+ `Location`), 204, 400, 401, 403, 404, 409, **422 para validaciones**, 429 (rate limit).
- Formato de error uniforme: `{ "code": "snake_case_en_ingles", "message": "texto en español", "details": [...] }` vía exception handlers globales. Nunca stacktraces.
- OpenAPI autogenerado por FastAPI, con `summary`, `description` y `response_model` en cada endpoint.

## 8. Autenticación y aislamiento de datos

- Contraseñas hasheadas con bcrypt/argon2. Política mínima: 8 caracteres. Nunca almacenar ni loguear la contraseña en claro.
- JWT firmado HS256: access token 15 min, refresh token 7 días rotativo. Claims mínimos: `sub` (user_id), `exp`, `iat`, `jti`.
- Dependencia `get_current_user` que resuelve el usuario desde el token y devuelve 401 si es inválido/expirado.
- **REGLA CRÍTICA — aislamiento multiusuario**: *toda* consulta a `categories`, `transactions`, `budgets`, `recurring_rules` y `chat_messages` filtra por `user_id` del token. Nunca se confía en un `user_id` que venga del body, la query o el prompt del chat. Un usuario que pide un recurso de otro recibe **404** (no 403, para no filtrar existencia).
- Debe existir un test de integración que verifique que el usuario A no puede leer, editar ni borrar recursos del usuario B, **en los cinco recursos**.

## 9. Movimientos recurrentes

### Estrategia: materialización, no virtualización

Las reglas **generan movimientos reales** en `transactions`. No se calculan al vuelo en cada consulta. Motivo: reportes, export CSV y las tools del chatbot leen todos de `transactions`; con ocurrencias virtuales habría que replicar la lógica de proyección en cada camino y las cifras se desincronizarían.

### Regla de oro: nunca se materializa el futuro

**El job solo genera ocurrencias con `occurred_on <= hoy`** (hoy = `Clock.today()` en `APP_TIMEZONE`). Esto resuelve de raíz el problema del balance: si materializaras el sueldo del día 1 con anticipación, el balance de hoy mostraría plata que todavía no cobraste.

Los vencimientos futuros se exponen **únicamente** por `GET /recurring-rules/upcoming`, calculados al vuelo, etiquetados como proyección, y **no participan de ningún reporte, del balance ni del export CSV**.

### El job de generación

- Corre **una vez por día** vía APScheduler, arrancado en el `lifespan` de FastAPI, a `RECURRING_JOB_HOUR` (default 03:00) en `APP_TIMEZONE`.
- Invocable manualmente para tests y desarrollo: caso de uso `GenerateRecurringTransactions(as_of: date)` que el job simplemente llama. **Los tests testean el caso de uso, no el scheduler.**
- **Idempotencia**: antes de insertar, verifica `recurring_occurrences`. La UNIQUE `(rule_id, occurred_on)` es la red de seguridad a nivel base — si dos ejecuciones concurrentes intentan la misma ocurrencia, la segunda falla con `IntegrityError` y se descarta silenciosamente. **El job tiene que poder correr 50 veces seguidas sin duplicar un solo movimiento.**
- **Catch-up**: genera las ocurrencias pendientes desde la última generada hasta hoy, **con tope de `RECURRING_CATCHUP_MAX_DAYS` (default 90)**. Si la app estuvo caída más que eso, loguea warning y genera solo los últimos 90 días, para que un contenedor apagado 8 meses no inyecte cientos de movimientos de golpe.
- Si una regla referencia una categoría borrada, se desactiva y se loguea. **Un error en una regla no puede impedir la generación de las demás** — procesá regla por regla con manejo de error individual.
- Con más de una réplica del backend haría falta un lock distribuido. Con una réplica, la UNIQUE alcanza. **Documentalo en el README.**

### Aritmética de calendario (función pura en `domain/`)

- `MONTHLY` con `day_of_month = 31` en un mes que no lo tiene → **se ajusta al último día del mes** (28/29/30). Nunca se saltea.
- `starts_on` inclusive; `ends_on` inclusive; regla con `ends_on` pasado se ignora.
- `is_active = false` pausa la generación **sin borrar** las ocurrencias ya creadas.
- Cambiar el `amount` afecta solo a ocurrencias futuras. Las ya generadas no se tocan.

### Ocurrencias individuales

- **Editar una ocurrencia** = editar el movimiento generado. Es una transacción normal.
- **Saltear una ocurrencia** = borrar el movimiento generado. El `DELETE /transactions/{id}` de un movimiento con `recurring_rule_id` marca la ocurrencia como `SKIPPED` en el ledger, para que **el job no la vuelva a crear**. Este es el bug más probable de toda la feature: si borrás el alquiler y al otro día reaparece, el ledger está mal implementado.
- **Borrar una regla** no borra los movimientos históricos: quedan como movimientos sueltos con `recurring_rule_id = NULL`.

## 10. Presupuestos

- Tope mensual de gasto para una categoría `EXPENSE`, en una moneda, en un mes calendario.
- `GET /budgets/progress?period_month=2026-08&currency=ARS` devuelve, por categoría con presupuesto: `budgeted`, `spent`, `remaining`, `percentage`, `status` (`OK` < 80%, `WARNING` 80–100%, `EXCEEDED` > 100%) y `currency`.
- El gasto se calcula sobre movimientos **reales** del mes (`type = EXPENSE`, misma moneda), incluidos los generados por reglas recurrentes. **Las proyecciones futuras no cuentan.**
- Categorías sin presupuesto definido aparecen aparte, con lo gastado, para que el usuario vea qué le falta presupuestar.
- `POST /budgets/copy-from` con `{ from_period, to_period, currency }` copia los presupuestos de un mes a otro; las categorías que ya tengan presupuesto en el destino se saltean (no se pisan) y se informan en la respuesta.
- En el front: barras de progreso con el color del `status`, y en el dashboard un resumen de categorías excedidas.

## 11. Asistente conversacional (LangChain + OpenAI)

Endpoint `POST /chat` con body `{ "message": "...", "conversation_id": "..." }`.

### Diseño obligatorio: agente con tools, NO text-to-SQL libre

Implementá un agente LangChain (tool calling) cuyas herramientas son funciones Python que reciben el `user_id` **inyectado desde el token al construir el agente** — el `user_id` nunca es un parámetro que el LLM pueda elegir. Lo mismo aplica a `currency`, que se fija en `DEFAULT_CURRENCY`. Herramientas:

| Tool | Descripción |
|------|-------------|
| `get_period_summary(date_from, date_to)` | Ingresos, gastos y balance del período |
| `get_spending_by_category(date_from, date_to, limit)` | Gasto agregado por categoría, desc |
| `search_transactions(filters)` | Búsqueda acotada de movimientos (máx N) |
| `get_monthly_trend(months)` | Serie mensual de ingresos/gastos |
| `compare_periods(period_a, period_b)` | Comparación entre dos períodos |
| `get_budget_status(period_month)` | Presupuestado vs gastado por categoría, con desvíos |
| `get_upcoming_commitments(days)` | Vencimientos recurrentes proyectados de los próximos N días |

Motivo del diseño: un agente SQL con acceso libre a la base convierte cualquier prompt injection en fuga de datos entre usuarios. Las tools con `user_id` cerrado hacen ese ataque imposible por construcción. Si aun así preferís `SQLDatabaseToolkit`, tiene que ser sobre un usuario MySQL de **solo lectura** apuntando a **vistas ya filtradas por `user_id`**, y hay que justificarlo.

**Toda tool devuelve los montos con su `currency` al lado**, para que el modelo nunca enuncie una cifra sin moneda.

### Comportamiento

- System prompt en **español rioplatense neutro**: rol de asesor financiero personal, responde **solo** con datos obtenidos de las tools, admite explícitamente cuando no tiene el dato, no inventa cifras, no da asesoramiento de inversión.
- **Las recomendaciones de ahorro se apoyan primero en los presupuestos** (`get_budget_status`): un desvío contra un tope que el usuario mismo fijó es mucho más accionable que "gastaste mucho en Ocio". Si no hay presupuestos del período, cae en el análisis comparativo (`compare_periods`, `get_spending_by_category`) y **sugiere definir presupuestos**.
- Si la consulta involucra compromisos futuros ("¿me alcanza para fin de mes?"), combina `get_period_summary` con `get_upcoming_commitments`, dejando claro qué parte es real y qué parte es proyección.
- **Fechas relativas** ("este mes", "el mes pasado", "últimos 3 meses") resueltas **en el backend** con el `Clock` en `APP_TIMEZONE`, y pasadas al contexto del agente. El modelo no calcula fechas.
- Historial persistido por usuario, con ventana acotada.
- Timeout y fallback con mensaje claro si OpenAI falla — nunca un 500 pelado.
- La API key de OpenAI vive **solo** en el backend, por variable de entorno. Jamás en el frontend, en el repo ni en los logs.

### Modelo y límites de consumo

- **Modelo: escalón `mini`**, configurado en `OPENAI_MODEL`. Cambiar de modelo tiene que ser editar el `.env`, **nunca** tocar código. Verificá el identificador exacto y el precio vigente en `platform.openai.com/pricing` al momento de implementar; no lo hardcodees a partir de este documento.
- Guardrails obligatorios, todos por variable de entorno:

| Límite | Variable | Default |
|---|---|---|
| Tokens máximos de respuesta | `OPENAI_MAX_TOKENS` | 500 |
| **Iteraciones máximas del agente** | `AGENT_MAX_ITERATIONS` | **3** |
| Mensajes de historial reenviados | `CHAT_HISTORY_WINDOW` | 6 |
| Consultas por usuario por hora | `CHAT_RATE_LIMIT_PER_HOUR` | 20 |

  El tope de **iteraciones** es el crítico: un agente sin límite puede entrar en loop tool→modelo→tool y hacer 50 llamadas en una sola consulta. Ese es el escenario a impedir, mucho más que el costo del uso normal.

- **Telemetría desde el día uno**: cada request al chat persiste una fila en `chat_usage` con `prompt_tokens`, `completion_tokens`, `total_tokens`, `tool_calls_count`, `model` y `latency_ms`, tomados de `response.usage`. Además, log estructurado con los mismos campos.
- En el README, una query SQL lista para copiar que devuelva consumo promedio por consulta, por usuario y por día, más la nota: **revisar a la semana de uso real y recalibrar modelo y límites con esos datos.**

## 12. Frontend

- SPA con React Router v6. Rutas públicas: `/login`, `/register`. Privadas bajo guard: `/dashboard`, `/transactions`, `/categories`, `/budgets`, `/recurring`, `/reports`, `/chat`.
- Cliente HTTP centralizado (`services/api.ts`) con interceptor que adjunta el access token y refresca automáticamente ante 401.
- Persistencia del token: preferí `httpOnly cookie` si implementás el backend acorde; si usás `localStorage`, documentá el trade-off de XSS en el README.
- **`utils/format.ts` es la única fuente de formateo**: `formatMoney(amount, currency)` y `formatDate(iso)` con locale `es-AR`. Ningún componente formatea montos ni fechas por su cuenta.
- Pantallas:
  - **Dashboard**: tarjetas de ingresos/gastos/balance del mes, torta por categoría, barras de tendencia mensual, **resumen de presupuestos excedidos** y **próximos vencimientos**.
  - **Movimientos**: tabla paginada con filtros (fechas, categoría, tipo, monto, texto), alta/edición en modal, borrado con confirmación, **ícono que distingue los generados por una regla**, botón "Exportar CSV".
  - **Categorías**: ABM con validación de duplicados y bloqueo de borrado si tiene movimientos, presupuestos o reglas.
  - **Presupuestos**: selector de mes, barras de progreso por categoría con color según `status`, ABM inline, botón "copiar del mes anterior".
  - **Recurrentes**: ABM de reglas con **preview de las próximas 3 fechas** que va a generar (feedback inmediato de que la regla quedó bien), toggle de pausa, historial de ocurrencias.
  - **Reportes**: gráficos con selector de período.
  - **Chat**: historial, indicador de "escribiendo", manejo de error y de rate limit.
- Estados de carga con skeletons, estados vacíos y estados de error explícitos en cada vista. Nada de pantallas en blanco.
- Formularios con validación cliente + manejo de los 422 del backend mapeados campo a campo **por `code`, no por el texto del mensaje**.
- Accesibilidad básica: labels asociados, foco visible, navegación por teclado en modales.
- Responsive mobile-first.

## 13. Infraestructura y entorno

- `docker-compose.yml` con tres servicios: `db` (mysql:8, volumen persistente, healthcheck, `TZ` seteado), `backend` (espera el healthcheck de db, corre migraciones al arrancar, levanta el scheduler, `TZ` seteado), `frontend` (build + nginx sirviendo estáticos con proxy a `/api`).
- Dockerfiles multi-stage, imagen final sin toolchain de build, proceso con usuario no-root.
- `.env.example` con **todas** las variables documentadas y valores dummy:

```
DATABASE_URL, JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS, AGENT_MAX_ITERATIONS,
CHAT_HISTORY_WINDOW, CHAT_RATE_LIMIT_PER_HOUR,
RECURRING_JOB_HOUR, RECURRING_CATCHUP_MAX_DAYS,
APP_TIMEZONE=America/Argentina/Buenos_Aires,
DEFAULT_CURRENCY=ARS, SUPPORTED_CURRENCIES=ARS,
CORS_ORIGINS, LOG_LEVEL
```

- `.gitignore` que excluya `.env`, `__pycache__`, `node_modules`, `dist`, `.venv`.
- **Ningún secreto real en el repositorio, en ningún commit.** Configuración por variables de entorno.
- Logging estructurado JSON, con `request_id`. **Prohibido loguear tokens, contraseñas, el contenido de los prompts del usuario o montos asociados a un email identificable.**
- Headers de seguridad: CORS restringido por env, `X-Content-Type-Options`, `X-Frame-Options`, HSTS en despliegue con TLS.
- `GET /health` con chequeo de DB y **estado del scheduler** (última ejecución exitosa del job).

## 14. Testing (obligatorio, no opcional)

- Patrón **AAA** (Arrange, Act, Assert). Un comportamiento por test, nombre descriptivo.
- Backend: unitarios de casos de uso con repositorios fake (sin DB), e integración de endpoints con `httpx.AsyncClient` contra MySQL de test en contenedor. Cobertura mínima **80%** en `domain/` y `application/`.
- Frontend: componentes con Testing Library y **MSW**. Nada de pegarle a la API real ni a OpenAI.

Casos que sí o sí hay que cubrir:

**Base**
- Aislamiento entre usuarios en los cinco recursos.
- Montos con decimales y bordes (0.01, valores grandes).
- Fechas límite del período (primer y último día).
- Categoría con movimientos / presupuestos / reglas que no se puede borrar.
- Token expirado e inválido.
- Paginación en el límite y `totalCount` consistente con los filtros.
- CSV con caracteres especiales, comas y comillas en la descripción.

**Moneda**
- `Money` rechaza más de 2 decimales, no finitos y la construcción desde `float`.
- `Money` admite negativos (un balance puede serlo); son las entidades las que exigen montos positivos.
- **Sumar o comparar `Money` de distinta moneda lanza `CurrencyMismatchError`.**
- `?currency=USD` → 422 `unsupported_currency` mientras `SUPPORTED_CURRENCIES=ARS`.
- Toda respuesta con montos incluye el campo `currency`.
- Test de regresión: **ninguna query de agregación suma montos sin filtrar por `currency`.**

**Zona horaria**
- Con `freezegun` en 23:50 y en 00:10 del día siguiente, `Clock.today()` devuelve la fecha correcta en `America/Argentina/Buenos_Aires`.
- La resolución de "este mes" / "el mes pasado" del chatbot es consistente con `Clock`.

**Recurrentes** (con `freezegun`)
- **Idempotencia**: correr el job 3 veces seguidas genera exactamente lo mismo que correrlo 1 vez.
- **Nunca genera futuro**: ningún movimiento generado tiene `occurred_on > hoy`.
- **Ocurrencia salteada no revive**: borrar un movimiento generado y reejecutar el job no lo recrea.
- **Día 31 en febrero**: una regla mensual día 31 genera el 28 (o 29 en bisiesto).
- **Catch-up con tope**: simular 200 días sin correr, verificar que genera solo los últimos 90 y loguea el warning.
- **Aislamiento de fallos**: una regla con categoría inválida no impide que las otras se generen.
- `is_active=false` no genera; reactivar no dispara backfill del período pausado.

**Presupuestos**
- `percentage` y `status` en los bordes exactos (79.9 / 80 / 100 / 100.1).
- Presupuesto sobre categoría `INCOME` → 422.
- `copy-from` no pisa presupuestos existentes en el destino.
- Mes sin presupuestos → respuesta vacía bien formada, no error.

**Chat**
- El LLM va **mockeado**. Se testea que las tools devuelven los agregados correctos y que el endpoint arma bien el contexto, **no la redacción del modelo**.
- Se persiste la fila en `chat_usage` con los tokens del `usage`.
- Al superar `AGENT_MAX_ITERATIONS`, el agente corta y devuelve fallback (no cuelga ni loopea).
- Al superar el rate limit → 429.
- **Las tools nunca devuelven datos de otro usuario**, aunque el mensaje pida explícitamente "los gastos del usuario 2".

CI en GitHub Actions: lint (`ruff` + `mypy` back, `eslint` + `tsc` front), tests de ambos lados y build de las imágenes Docker. **El PR no se mergea con el pipeline en rojo.**

## 15. Git y flujo de trabajo

- Trunk-based: ramas de vida corta desde `main`, PR obligatorio, squash merge, historial lineal.
- **Conventional Commits** obligatorio: `<type>[scope]: <descripción en imperativo>`. Tipos: `feat`, `fix`, `test`, `chore`, `docs`, `style`, `refactor`, `perf`, `build`, `ci`, `revert`. `BREAKING CHANGE:` en el footer cuando corresponda.
  - Ejemplos: `feat(budgets): agregar endpoint de progreso mensual`, `fix(recurring): evitar duplicados al reejecutar el job`, `test(money): cubrir mismatch de moneda`.
- Un commit por unidad lógica de cambio; no mezclar refactor con feature.

## 16. Servidores MCP

Durante el desarrollo usá al menos dos servidores MCP:
- **GitHub MCP**: creación y gestión del repositorio, ramas, PRs, revisión de issues y análisis del historial.
- **Filesystem MCP**: lectura y escritura de los archivos del proyecto.

Documentá en el README qué servidores MCP se usaron y para qué, con la configuración necesaria (sin tokens reales).

## 17. Casos de uso y criterios de aceptación

Implementá los 12 casos de uso. Cada uno se considera terminado cuando cumple su criterio **y tiene tests que lo demuestran**.

| # | Caso de uso | Criterio de aceptación |
|---|-------------|------------------------|
| 1 | Registro de usuario | `POST /auth/register` crea el usuario con contraseña hasheada y siembra categorías por defecto. Email duplicado → 409. Email o contraseña inválidos → 422. |
| 2 | Inicio de sesión | Credenciales válidas → 200 con access + refresh token. Inválidas → 401 con mensaje genérico (sin revelar si el email existe). |
| 3 | Registrar ingreso | `POST /transactions` con `type=INCOME`, monto > 0, fecha, categoría propia y descripción → 201. Categoría ajena o de otro tipo → 422. Moneda no soportada → 422. |
| 4 | Registrar gasto | Ídem con `type=EXPENSE`. El balance del resumen y el progreso del presupuesto reflejan el nuevo movimiento. |
| 5 | Editar / eliminar movimientos | `PATCH` y `DELETE` solo sobre movimientos propios; sobre ajenos → 404. Los reportes reflejan el cambio de inmediato. Borrar uno generado por una regla lo marca `SKIPPED` y no reaparece. |
| 6 | Administrar categorías | ABM completo. Nombre duplicado por tipo → 409. Borrar categoría con movimientos, presupuestos o reglas → 409 con mensaje accionable. |
| 7 | Visualizar reportes | Los tres endpoints devuelven agregados correctos para el período y la moneda, y el front los grafica. Período sin datos → respuesta vacía bien formada, no error. |
| 8 | Filtrar y buscar | Todos los filtros del §7 funcionan combinados, con paginación correcta y `totalCount` consistente con los filtros aplicados. |
| 9 | Exportar CSV | `GET /transactions/export` devuelve `text/csv` con `Content-Disposition: attachment`, respetando los filtros activos, UTF-8 con BOM (para Excel), escape correcto de comas/comillas, columna de moneda, y **sin proyecciones futuras**. |
| 10 | Asistente inteligente | Las consultas de ejemplo devuelven cifras que coinciden exactamente con los endpoints de reportes y presupuestos para el mismo período. Nunca accede a datos de otro usuario. Cada consulta deja su fila en `chat_usage`. |
| 11 | Movimientos recurrentes | Una regla activa genera exactamente un movimiento por ocurrencia vencida, nunca futura, sin duplicados al reejecutar, respetando pausas, `ends_on` y el ajuste de día 31. El preview del front coincide con lo que después genera el job. |
| 12 | Presupuestos por categoría | El usuario define un tope mensual por categoría de gasto; `GET /budgets/progress` devuelve gastado, restante, porcentaje y estado correctos, y el asistente los usa para sus recomendaciones. |

Consultas que el asistente debe responder correctamente (casos de prueba del CU10):
- ¿Cuánto gasté este mes?
- ¿Cuál fue mi categoría con mayor gasto?
- ¿Cuánto dinero ahorré el mes pasado?
- ¿En qué podría reducir mis gastos?
- ¿Cómo voy con mi presupuesto de este mes?
- ¿Qué gastos fijos me quedan por pagar?

## 18. Plan de ejecución por fases

Ejecutá en este orden, con commit y tests verdes al cierre de cada fase.

**El orden no es arbitrario**: el asistente (fase 10) va **antes** que los recurrentes (fase 12) porque es el diferencial del producto. Los recurrentes son la feature más costosa y la menos visible: si el proyecto se aprieta, es lo único que se recorta, y todo lo demás ya quedó entregado y funcionando.

1. **Scaffolding**: estructura de carpetas, `docker-compose`, `.env.example`, health check, CI mínima corriendo.
2. **Dominio y persistencia**: **`Money` VO y puerto `Clock` primero**, entidades con sus invariantes, modelos SQLAlchemy con `currency`, mappers dominio↔ORM, migración inicial de Alembic + tests unitarios y de constraints.
   *Los repositorios concretos NO van acá*: sus firmas las determinan los casos de uso que los consumen (filtros, paginación, agregaciones), así que cada uno se implementa en la fase de su feature. Escribirlos antes sería adivinar la interfaz.
3. **Autenticación**: registro, login, refresh, `get_current_user`, seed de categorías + tests de aislamiento.
4. **Categorías**: ABM completo + tests.
5. **Transacciones**: CRUD, filtros, paginación + tests.
6. **Reportes y export CSV** + tests.
7. **Presupuestos (backend)**: ABM, `progress`, `copy-from` + tests de bordes.
8. **Frontend base**: routing, guard, cliente HTTP, `utils/format.ts`, login/registro, layout.
9. **Frontend features**: dashboard, movimientos, categorías, reportes, presupuestos + tests con MSW.
10. **Asistente LangChain**: las 7 tools, agente, endpoint, historial, guardrails y telemetría de tokens + tests con LLM mockeado.
11. **Frontend chat** + pulido de UX, estados vacíos y de error.
12. **Recurrentes (backend)**: aritmética de calendario en `domain/`, ABM de reglas, ledger de ocurrencias, caso de uso de generación, job de APScheduler, `upcoming` + batería completa de tests con `freezegun`.
13. **Frontend recurrentes**: ABM con preview de próximas fechas, historial de ocurrencias, próximos vencimientos en el dashboard.
14. **Cierre**: README completo (query de consumo de tokens, nota de recalibración, roadmap de USD y su pregunta abierta de tipo de cambio), OpenAPI revisada, verificación end-to-end con `docker compose up` desde cero.

## 19. Decisiones cerradas — no volver a preguntar

| Tema | Decisión |
|---|---|
| Alcance | Movimientos simples **+ presupuestos + recurrentes** — 12 casos de uso |
| Modelo de IA | Escalón **mini**, configurable por `OPENAI_MODEL`, con telemetría en `chat_usage` desde la fase 10 y recalibración con datos reales a la semana |
| Moneda | **ARS única en v1**, con esquema y dominio preparados para USD (§5.1). Sin conversión ni cotizaciones |
| Zona horaria | **Fija del servidor**: `America/Argentina/Buenos_Aires`, vía puerto `Clock` (§5.2) |
| Idioma | **Solo español**, locale `es-AR`, sin i18n (§5.3) |

## 20. Restricciones finales

- No implementes funcionalidad que no esté en los 12 casos de uso. Si detectás algo faltante, proponelo — no lo agregues por tu cuenta.
- No uses `float` para dinero, en ninguna capa. Usá `Money`.
- **No sumes montos sin filtrar por moneda**, aunque hoy solo exista ARS.
- **No implementes conversión de monedas ni cotizaciones.** Está explícitamente fuera de alcance.
- **No llames a `date.today()` / `datetime.now()` fuera de la implementación de `Clock`, ni calcules fechas en SQL.**
- No mandes montos formateados ni fechas localizadas por el JSON: ISO en la API, `es-AR` solo en la vista.
- No instales librerías de i18n.
- No devuelvas datos de un usuario a otro, por ningún camino — incluido el chat.
- **No materialices movimientos con fecha futura.** Las proyecciones se calculan al vuelo y nunca entran a reportes, balance ni export.
- No hardcodees secretos ni los subas al repo. Tampoco el identificador del modelo de OpenAI: va por env.
- No declares una fase terminada sin haber corrido los tests y visto la salida.
