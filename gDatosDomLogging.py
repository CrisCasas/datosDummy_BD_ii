#!/usr/bin/env python3
"""
populate_logging.py  ·  dominio logging  ·  PostgreSQL ≥ 13

• Inserta:
    – 30 000 registros en activity_log
    – 20 000 registros en authentication_log
    – 15 000 registros en version_history
• Conexión:
    – Primero intenta POSTGRES_URL (p. ej. postgresql://user:pwd@host:5432/db)
    – Si no existe, usa DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASS
• Esquema:
    – Usa search_path = public (tablas creadas previamente)
"""

from __future__ import annotations
import os, random, hashlib, ipaddress
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote

import psycopg2
from faker import Faker
from dotenv import load_dotenv

# ------------------------------------------------------------------ #
# 1. Conexión                                                        #
# ------------------------------------------------------------------ #
load_dotenv()                     # lee .env si existe
faker = Faker("en_US")
Faker.seed(2025); random.seed(2025)

def build_dsn() -> dict:
    """Parsea POSTGRES_URL o variables sueltas y devuelve kwargs para psycopg2."""
    url = os.getenv("POSTGRES_URL")
    if url and urlparse(url).scheme.startswith("postgres"):
        p = urlparse(url)
        return dict(
            host=p.hostname, port=p.port or 5432,
            dbname=p.path.lstrip("/"),
            user=p.username,
            password=unquote(p.password) if p.password else None,
            options="-c search_path=public"
        )
    # fallback
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "postgres"),
        options="-c search_path=public"
    )

conn = psycopg2.connect(**build_dsn())
conn.autocommit = False
cur = conn.cursor()

# ------------------------------------------------------------------ #
# 2. Parámetros de volumen                                           #
# ------------------------------------------------------------------ #
N_ACTIVITY       = 30_000
N_AUTH           = 20_000
N_VERSION        = 15_000
BATCH_SIZE       = 2_000          # filas por lote
USER_ID_RANGE    = (1, 5_000)     # rango coherente con dominio_usuario
FILE_ID_RANGE    = (1, 20_000)    # si existen ids reales pon el rango correcto

ACT_TYPES  = ["upload", "download", "delete", "share", "rename"]
RES_TYPES  = ["file", "folder"]
AUTH_TYPES = ["login", "logout", "mfa"]
MIME_TYPES = [".pdf", ".jpg", ".txt", ".xls", ".zip"]  # solo para path ficticio

# ------------------------------------------------------------------ #
# 3. Funciones auxiliares                                            #
# ------------------------------------------------------------------ #
def random_ipv4() -> str:
    return str(ipaddress.IPv4Address(random.randint(0x0B000000, 0xDF000000)))  # evita redes reservadas

def md5_hex() -> str:
    return hashlib.md5(faker.sha1().encode()).hexdigest()

def ts_within(days_back: int = 365) -> datetime:
    return datetime.utcnow() - timedelta(days=random.randint(0, days_back),
                                         seconds=random.randint(0, 86_400))

def execute_batch(sql: str, rows: list[tuple]):
    args = b",".join(cur.mogrify("(%s)" % (",".join(["%s"]*len(r))), r) for r in rows)
    cur.execute(sql % args.decode())

# ------------------------------------------------------------------ #
# 4. SQL precompilado                                                #
# ------------------------------------------------------------------ #
SQL_ACTIVITY = """INSERT INTO activity_log
(user_id, activity_type, resource_id, resource_type, timestamp, ip_address, user_agent)
VALUES %s;"""

SQL_AUTH = """INSERT INTO authentication_log
(user_id, action_type, timestamp, ip_address, user_agent, success)
VALUES %s;"""

SQL_VERSION = """INSERT INTO version_history
(file_id, created_by, created_at, version_path, size, checksum)
VALUES %s;"""

# ------------------------------------------------------------------ #
# 5. Inserción por lotes                                             #
# ------------------------------------------------------------------ #
def populate(table: str, total: int, builder):
    batch, inserted = [], 0
    while inserted < total:
        batch.append(builder())
        if len(batch) == BATCH_SIZE or inserted + len(batch) == total:
            if table == "activity":
                execute_batch(SQL_ACTIVITY, batch)
            elif table == "auth":
                execute_batch(SQL_AUTH, batch)
            else:
                execute_batch(SQL_VERSION, batch)
            inserted += len(batch)
            conn.commit()
            print(f"{table}: {inserted}/{total}")
            batch.clear()

# Generadores de filas ----------------------------------------------
def build_activity() -> tuple:
    return (
        random.randint(*USER_ID_RANGE),
        random.choice(ACT_TYPES),
        random.randint(1, 100_000),
        random.choice(RES_TYPES),
        ts_within(),
        random_ipv4(),
        faker.user_agent()
    )

def build_auth() -> tuple:
    return (
        random.randint(*USER_ID_RANGE),
        random.choice(AUTH_TYPES),
        ts_within(),
        random_ipv4(),
        faker.user_agent(),
        random.random() < 0.92  # 92 % éxito
    )

def build_version() -> tuple:
    fid = random.randint(*FILE_ID_RANGE)
    return (
        fid,
        random.randint(*USER_ID_RANGE),
        ts_within(),
        f"s3://bucket/{fid}/v{random.randint(1,10)}{random.choice(MIME_TYPES)}",
        random.randint(1_000, 50_000_000),  # bytes
        md5_hex()
    )

# ------------------------------------------------------------------ #
# 6. Ejecutar población                                              #
# ------------------------------------------------------------------ #
populate("activity", N_ACTIVITY, build_activity)
populate("auth",     N_AUTH,     build_auth)
populate("version",  N_VERSION,  build_version)

cur.close(); conn.close()
print("Carga completada ✔")
