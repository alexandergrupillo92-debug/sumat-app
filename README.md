# Sistema Tributario tipo SUMAT — Despliegue

## Archivos incluidos
- `app.py` — Flask + SQLAlchemy + auditoría fiscal + generación de PDF (ReportLab)
- `templates/index.html` — formulario de auditoría
- `templates/historial.html` — listado de declaraciones registradas
- `sql/schema.sql` — script para crear las tablas en Supabase
- `requirements.txt`

## Pasos que debes hacer tú manualmente

### 1. Supabase
1. Crea una cuenta en supabase.com y un proyecto nuevo (gratuito).
2. Ve a **SQL Editor** y pega el contenido de `sql/schema.sql`, luego "Run".
3. Ve a **Project Settings > Database > Connection string** y copia la URI
   (modo "URI", no "Session pooler"). Se ve así:
   `postgresql://postgres:[TU-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`

### 2. GitHub
1. Sube esta carpeta a un repositorio nuevo (`git add . && git commit -m "sumat inicial" && git push`).

### 3. Render
1. Crea un nuevo **Web Service** apuntando a tu repositorio.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app`
4. En **Environment**, agrega la variable:
   - `DATABASE_URL` = la URI de Supabase que copiaste (cambia `postgres://` por
     `postgresql://` si Supabase te la da con ese prefijo — el código ya lo
     corrige automáticamente por si acaso).
5. Deploy. Render te dará una URL pública tipo `https://tu-app.onrender.com`.

## Notas
- La alícuota (2%) y el recargo (50%) están como constantes al inicio de
  `app.py` (`ALICUOTA`, `RECARGO_PCT`) — cámbialas ahí si la normativa exige
  otros porcentajes.
- `db.create_all()` en `app.py` es un respaldo idempotente: no rompe nada si
  ya corriste `schema.sql`, y crea las tablas si por algún motivo no existieran.
- El PDF se genera en memoria (`io.BytesIO`), sin escribir archivos temporales
  en el servidor.
