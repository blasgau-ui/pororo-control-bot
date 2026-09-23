# Pororo Control — Bot de Telegram

Bot de Telegram para manejar productos, stock, ventas y gastos de **pororo-control** sin
abrir la web. Todo lo que se carga acá se guarda en la misma cuenta de pororo-control, así
que aparece al instante en la página (y viceversa: lo que se carga en la web se ve al toque
acá, por ejemplo con `/resumen` o `/productos`).

## Cómo funciona (y por qué está armado así)

pororo-control es una aplicación web sin servidor propio: el navegador lee y escribe
directamente en Supabase (la tabla `pororo_control_state`, una fila JSON por cuenta,
protegida con Row Level Security para que cada cuenta solo pueda ver y modificar la suya).
No existe una "API de pororo-control" aparte de eso.

Por eso este bot habla directo con Supabase, autenticado como la cuenta de cada
usuaria (con su email y contraseña, igual que en la web). Así los cambios quedan en la
misma fila que lee la web y se ven reflejados al instante, sin necesidad de sincronizar
nada aparte.

Toda esa integración vive en un solo archivo, `bot/supabase_service.py`, separado del
resto del bot (`bot/domain.py` con la lógica de negocio pura, y `bot/handlers/*` con las
conversaciones de Telegram). Si en el futuro pororo-control pasa a tener una API propia,
sólo hay que reescribir ese archivo.

## Instalación

Requiere Python 3.11 o más nuevo.

```bash
cd telegram-bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Completá `.env`:

- `TELEGRAM_BOT_TOKEN`: lo da [@BotFather](https://t.me/BotFather) en Telegram al crear el bot (`/newbot`).
- `SUPABASE_URL` / `SUPABASE_ANON_KEY`: los mismos que usa la web (ya vienen pre-cargados
  en `.env.example` con los de pororo-control; si en algún momento cambian, se actualizan acá también).
- `BOT_ENCRYPTION_KEY`: clave para cifrar en disco las sesiones vinculadas. Generar una vez con:

  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

  No la cambies después de tener gente usando el bot: si cambia, las sesiones guardadas
  quedan ilegibles y cada quien tiene que hacer `/login` de nuevo (no se pierde ningún
  dato de pororo-control, solo hay que volver a iniciar sesión en el bot).

## Correrlo

```bash
python main.py
```

Usa *long polling* (el bot se conecta él mismo a Telegram a buscar mensajes), así que no
hace falta abrir ningún puerto ni tener un dominio: sirve para correrlo en una notebook,
un Raspberry Pi, un VPS chico, o un servicio como Railway o Render con un "worker"
(proceso de fondo) corriendo `python main.py` — no necesita ser un "web service" con puerto
HTTP.

⚠️ Telegram sólo permite **una** instancia haciendo long polling por bot a la vez. Si corrés
`python main.py` en tu máquina mientras el mismo bot ya está desplegado en otro lado, las
dos van a pelear por los mensajes (`telegram.error.Conflict`). Antes de correrlo local para
probar algo, apagá el despliegue (o viceversa).

### Ya desplegado en Railway

Este bot corre en Railway (proyecto `pororo-control-bot`, servicio del mismo nombre) como
un worker de fondo, sin servidor HTTP ni puerto expuesto — no depende de que ninguna
máquina personal esté prendida. Configuración relevante:

- `railway.json`: le dice a Railway que el comando de arranque es `python main.py`.
- `.railwayignore`: evita subir `.env`, `*.db` y `*.log` a la imagen — las variables reales
  viven sólo en Railway (`railway variable list`), nunca en el build.
- Un volumen (`pororo-control-bot-volume`) montado en `/data` guarda `bot_sessions.db` ahí
  (`BOT_DB_PATH=/data/bot_sessions.db`), así las sesiones vinculadas sobreviven a los
  redeploys en vez de perderse cada vez que se sube código nuevo.

Comandos útiles una vez logueado con `railway login` y parado en esta carpeta:

```bash
railway logs                          # ver logs en vivo
railway variable list --kv            # ver variables configuradas
railway up -y --ci --service pororo-control-bot   # redesplegar tras un cambio de código
```

### Alternativa: VPS propio con systemd

Si en algún momento se migra a un VPS en vez de Railway, un ejemplo de unit de systemd:

```ini
# /etc/systemd/system/pororo-bot.service
[Unit]
Description=Pororo Control Telegram Bot
After=network.target

[Service]
WorkingDirectory=/ruta/a/telegram-bot
ExecStart=/ruta/a/telegram-bot/.venv/bin/python main.py
Restart=always
RestartSec=5
EnvironmentFile=/ruta/a/telegram-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now pororo-bot
```

### Desplegar en Render (gratis)

Render no ofrece "Background Worker" en el plan free — sólo "Web Service" tiene tier
gratuito. Por eso `render.yaml` declara `type: web`, y `bot/health_server.py` levanta un
servidor HTTP mínimo en paralelo (sólo cuando Render define la variable `PORT`) para que
Render considere el servicio "vivo". El bot en sí sigue andando por long polling siempre;
ese servidor HTTP no hace nada más que responder "ok".

**Limitaciones reales del free tier** (a diferencia de Railway, que ya tiene un despliegue
con volumen persistente — ver más arriba):

- El servicio se "duerme" después de 15 minutos sin recibir tráfico HTTP, y ahí el bot dejar
  de responder en Telegram hasta que algo lo despierte. Solución simple: un servicio externo
  gratuito como [UptimeRobot](https://uptimerobot.com) pegándole a la URL pública cada 5-10
  minutos.
- El disco es efímero: no hay volumen persistente gratis, así que `bot_sessions.db` se
  borra en cada redeploy o cada vez que el servicio se duerme y despierta. Nadie pierde
  datos de pororo-control (eso vive en Supabase), pero sí hay que volver a hacer `/login`
  después de cada reinicio.

**Pasos:**

1. Crear el bot en Render: New → Blueprint → conectar este repo/carpeta (usa `render.yaml`
   automáticamente), o New → Web Service manual con Build Command
   `pip install -r requirements.txt` y Start Command `python main.py`.
2. Cargar las variables marcadas `sync: false` en el dashboard de Render (Environment):
   `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `BOT_ENCRYPTION_KEY` — los
   mismos valores que en tu `.env` local (nunca subas el `.env` en sí).
3. Deploy. Una vez que el log muestre `Application started`, probar `/start` en Telegram.
4. (Opcional pero recomendado) configurar un ping externo cada 5-10 min a la URL pública del
   servicio para que no se duerma.

⚠️ Nunca corras este bot en dos lugares a la vez con el mismo `TELEGRAM_BOT_TOKEN` (por
ejemplo acá y en Railway simultáneamente): Telegram sólo deja una instancia haciendo long
polling por bot, y la segunda tira `telegram.error.Conflict`. Elegí uno solo, o generá un
bot nuevo con @BotFather para el otro entorno.

## Uso

1. Cada persona escribe `/start` y después `/login` con el email y contraseña de su
   cuenta de pororo-control (la misma que usa en la web; si todavía no tiene cuenta, la
   crea primero desde la web).
2. Una vez logueada, el bot recuerda la sesión en ese chat (no hay que loguearse cada vez).
3. `/ayuda` lista todos los comandos.

Comandos principales: `/productos`, `/crear_producto`, `/editar_producto`, `/stock`,
`/ganancia`, `/gasto`, `/resumen`, `/exportar`, `/notificaciones`, `/logout`.

## Seguridad

- La contraseña nunca se guarda: solo se usa una vez, en el momento del login, para pedirle
  un token a Supabase. Lo que se guarda (cifrado con `BOT_ENCRYPTION_KEY`) son los tokens de
  sesión, revocables cerrando sesión en Supabase o con `/logout`.
- El bot intenta borrar automáticamente el mensaje donde la usuaria escribió su
  contraseña, apenas lo procesa.
- Row Level Security en Supabase es la barrera real: aunque hubiera un bug en el bot, la
  base de datos igual sólo deja leer/escribir la fila del usuario autenticado.
- Después de 5 intentos de login fallidos seguidos, ese chat queda bloqueado 15 minutos.
- El bot valida que los números cargados (cantidades, precios, montos) sean números
  válidos y no negativos antes de guardarlos.

### Limitación conocida

Si alguien edita datos en la web y en el bot casi al mismo tiempo, gana el último guardado
(no hay merge automático) — igual que pasaría con dos pestañas del navegador abiertas a la
vez. Para un uso familiar normal (una persona por cuenta, cargando de a un movimiento por
vez) no debería ser un problema en la práctica.

## Tests

```bash
pip install pytest
pytest
```

Cubren la lógica de negocio pura (`bot/domain.py`: cálculo de stock, resumen mensual,
formato de claves) y el guardado de sesiones (`bot/session_store.py`, `bot/crypto_utils.py`).
No hacen llamadas de red ni tocan la cuenta real de Supabase.

## Posibles mejoras futuras

- Multi-idioma (hoy todo está en español, como la web).
- Reporte semanal además del diario.
- Búsqueda de productos por nombre con `/buscar`.
- Historial de movimientos de stock de un producto puntual.
- Soporte para más de un negocio por persona (hoy es 1 cuenta de pororo-control = 1 cuenta
  de Telegram vinculada a la vez).
- Refresh proactivo de tokens en el job diario para que las sesiones duren indefinidamente
  sin que la usuaria tenga que volver a loguearse tras mucha inactividad.
