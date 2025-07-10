Tables Users
/* ========================================================================
   ARCHIVO   : dominio_usuario.sql
   PROPÓSITO : Crear/actualizar el dominio de usuarios, planes de
               suscripción y sesiones para el clon de Google Drive.
   USO       : psql -U <usuario> -d <base> -f dominio_usuario.sql
   AVISO     : El bloque de limpieza borra datos existentes.
               Coméntalo si necesitas conservar información.
   ======================================================================== */

-- ------------------------------------------------------------------------
-- 0. Limpieza previa (OPCIONAL) ------------------------------------------
--    Descomenta estas líneas si quieres que el script sea idempotente
--    en entornos de desarrollo o CI/CD. En producción, evalúa riesgos.
-- ------------------------------------------------------------------------

--DROP SCHEMA IF EXISTS public CASCADE;

-- ------------------------------------------------------------------------
-- 1. Creación de esquema y configuración de contexto ---------------------
-- ------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS public;
ALTER  SCHEMA public OWNER TO CURRENT_USER;
SET search_path TO public;

-- ------------------------------------------------------------------------
-- 2. Tabla principal: usuario -------------------------------------------
-- ------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS usuario (
    user_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    full_name       TEXT,
    profile_picture TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    is_activated    BOOLEAN NOT NULL DEFAULT TRUE,
    account_type    TEXT    NOT NULL DEFAULT 'free',
    storage_quota   BIGINT  NOT NULL DEFAULT 0 CHECK (storage_quota >= 0),
    used_storage    BIGINT  NOT NULL DEFAULT 0 CHECK (used_storage  >= 0)
);

COMMENT ON TABLE  usuario                  IS 'Usuarios de la plataforma';
COMMENT ON COLUMN usuario.storage_quota    IS 'Cuota total (MB/GB) asignada al usuario';

-- ------------------------------------------------------------------------
-- 3. Tabla: plan_suscripcion --------------------------------------------
-- ------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS plan_suscripcion (
    plan_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES usuario(user_id)
                                 ON UPDATE CASCADE
                                 ON DELETE CASCADE,
    name           TEXT   NOT NULL,
    description    TEXT,
    storage_limit  BIGINT NOT NULL CHECK (storage_limit >= 0),
    price          NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_plan_suscripcion_usuario_activo
    ON plan_suscripcion (user_id)
    WHERE is_active;

COMMENT ON TABLE plan_suscripcion IS 'Planes de suscripción contratados';

-- ------------------------------------------------------------------------
-- 4. Tabla: sesion_usuario ----------------------------------------------
-- ------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sesion_usuario (
    session_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES usuario(user_id)
                               ON UPDATE CASCADE
                               ON DELETE CASCADE,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    device_info  TEXT,
    ip_address   INET,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sesion_usuario_activa
    ON sesion_usuario (user_id)
    WHERE is_active;

COMMENT ON TABLE sesion_usuario IS 'Sesiones de autenticación de usuarios';

-- ------------------------------------------------------------------------
-- Fin del script
-- ------------------------------------------------------------------------

Tables Logging
/* =========================================================
   ESQUEMA  : logging
   TABLAS   : activity_log, authentication_log, version_history
   NOTA     : Este script es idempotente (usa IF NOT EXISTS)
              y NO define claves foráneas externas.
   ========================================================= */

-- 1. Crear esquema (opcional; comenta si prefieres usar "public")
CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

--------------------------------------------------------------
-- 2. Tabla: activity_log
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    log_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT       NOT NULL,        -- sin FK externa
    activity_type  TEXT         NOT NULL,        -- p.e.: 'upload', 'delete'
    resource_id    BIGINT,                       -- id lógico del recurso
    resource_type  TEXT,                         -- 'file', 'folder', etc.
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address     INET,
    user_agent     TEXT
);

CREATE INDEX IF NOT EXISTS idx_activity_user_ts
    ON activity_log (user_id, timestamp DESC);

--------------------------------------------------------------
-- 3. Tabla: authentication_log
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS authentication_log (
    auth_log_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT       NOT NULL,        -- sin FK externa
    action_type    TEXT         NOT NULL,        -- 'login', 'logout', etc.
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ip_address     INET,
    user_agent     TEXT,
    success        BOOLEAN      NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_user_ts
    ON authentication_log (user_id, timestamp DESC);

--------------------------------------------------------------
-- 4. Tabla: version_history
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS version_history (
    version_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id        BIGINT       NOT NULL,        -- sin FK externa
    created_by     BIGINT,                       -- id de usuario creador
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    version_path   TEXT         NOT NULL,        -- ubicación física/lógica
    size           BIGINT       NOT NULL DEFAULT 0 CHECK (size >= 0),
    checksum       TEXT
);

CREATE INDEX IF NOT EXISTS idx_version_file_ts
    ON version_history (file_id, created_at DESC);

-- Fin del script

Tables Analytics
/* =========================================================
   ESQUEMA : analytics
   TABLAS  : file_access_metrics
             user_usage_metrics
             sharing_activity_metrics
             system_performance_metrics
             tag_usage_metrics
   NOTA    : Idempotente. Ejecuta sin error si ya existe.
   ========================================================= */

-- 0. Crear esquema (comenta estas líneas si usarás "public")
CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

--------------------------------------------------------------
-- 1. Tabla : file_access_metrics
--    Métricas diarias por archivo
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS file_access_metrics (
    file_id                 BIGINT     NOT NULL,
    date                    DATE       NOT NULL,
    view_count              BIGINT     NOT NULL DEFAULT 0,
    download_count          BIGINT     NOT NULL DEFAULT 0,
    last_accessed_by_user   BIGINT,
    PRIMARY KEY (file_id, date)
);

--------------------------------------------------------------
-- 2. Tabla : user_usage_metrics
--    Resumen diario de uso por usuario
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_usage_metrics (
    metric_id           BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT     NOT NULL,
    date                DATE       NOT NULL,
    files_uploaded      BIGINT     NOT NULL DEFAULT 0,
    files_downloaded    BIGINT     NOT NULL DEFAULT 0,
    used_storage_mb     NUMERIC(20,2) NOT NULL DEFAULT 0,
    active_minutes      BIGINT     NOT NULL DEFAULT 0,
    login_count         BIGINT     NOT NULL DEFAULT 0,
    shared_items_count  BIGINT     NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_user_usage_uid_date
    ON user_usage_metrics (user_id, date);

--------------------------------------------------------------
-- 3. Tabla : sharing_activity_metrics
--    Actividad de compartición por usuario y día
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sharing_activity_metrics (
    metric_id       BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "timestamp"     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         BIGINT       NOT NULL,
    date            DATE         NOT NULL,
    links_created   BIGINT       NOT NULL DEFAULT 0,
    shared_files    BIGINT       NOT NULL DEFAULT 0,
    revoked_links   BIGINT       NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sharing_uid_date
    ON sharing_activity_metrics (user_id, date);

--------------------------------------------------------------
-- 4. Tabla : system_performance_metrics
--    Indicadores de salud de la plataforma
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_performance_metrics (
    record_id              BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "timestamp"            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_usage_percent      NUMERIC(5,2),
    disk_io_mb             NUMERIC(20,2),
    avg_response_time_ms   BIGINT,
    active_sessions        BIGINT,
    concurrent_uploads     BIGINT
);

--------------------------------------------------------------
-- 5. Tabla : tag_usage_metrics
--    Uso de etiquetas (tags) por día
--------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_usage_metrics (
    tag_id               BIGINT NOT NULL,
    date                 DATE   NOT NULL,
    assigned_to_files    BIGINT NOT NULL DEFAULT 0,
    assigned_to_folders  BIGINT NOT NULL DEFAULT 0,
    search_hits          BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (tag_id, date)
);

-- Índice para consultas por periodo
CREATE INDEX IF NOT EXISTS idx_tag_usage_date
    ON tag_usage_metrics (date DESC);

-- Fin del script
