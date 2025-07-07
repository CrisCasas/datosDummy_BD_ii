#!/usr/bin/env python3
"""
Carga masiva de datos de prueba en dominio_usuario.*

● 5 000 usuarios
● 1 plan por usuario (ponderado)
● 1-5 sesiones por usuario

Credenciales:
  – Se cargan desde variables de entorno.
  – Soporta DATABASE_URL de Railway.
  – Fallback explícito a DB_HOST, DB_PORT, etc.
"""

import os
import random
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote

import psycopg2
from faker import Faker
from dotenv import load_dotenv

# ------------------------------------------------------------------------
# 0. Variables de entorno y cadena de conexión
# ------------------------------------------------------------------------
load_dotenv()  # lee .env si existe

def build_dsn() -> dict:
    """
    Devuelve kwargs adecuados para psycopg2.connect.

    Prioridad:
      1) DATABASE_URL (formato postgresql://usuario:pass@host:puerto/db)
      2) DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
    """
    url = os.getenv("DATABASE_URL")
    if url:
        # Normaliza >> admite url codificada
        parsed = urlparse(url)
        return dict(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=unquote(parsed.password) if parsed.password else None,
            options="-c search_path=public",
        )

    # Variables sueltas
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "google_drive_clone"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "postgres"),
        options="-c search_path=public",
    )

conn = psycopg2.connect(**build_dsn())
conn.autocommit = False
cur = conn.cursor()

# ------------------------------------------------------------------------
# 1. Configuración de datos sintéticos
# ------------------------------------------------------------------------
faker = Faker("es_CO")
BATCH_SIZE = 500

PLANS = [
    ("Free",    "Plan gratuito",        5_000,     0.00),
    ("Básico",  "Hasta 100 GB",       100_000,     3.99),
    ("Premium", "Hasta 1 TB + extras", 1_000_000,  9.99),
]

def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()

def random_plan():
    r = random.random()
    return PLANS[0] if r < 0.60 else PLANS[1] if r < 0.90 else PLANS[2]

# ------------------------------------------------------------------------
# 2. SQL paramétrico (usaremos cur.mogrify para batch)
# ------------------------------------------------------------------------
user_sql = """INSERT INTO usuario
(email, password_hash, full_name, profile_picture,
 created_at, last_login, email_verified, is_activated,
 account_type, storage_quota, used_storage)
VALUES %s RETURNING user_id;"""

plan_sql = """INSERT INTO plan_suscripcion
(user_id, name, description, storage_limit, price, is_active)
VALUES %s;"""

session_sql = """INSERT INTO sesion_usuario
(user_id, is_active, device_info, ip_address,
 created_at, expires_at)
VALUES %s;"""

def execute_batch(template_sql: str, rows: list[tuple]):
    """Genera VALUES (…) con mogrify para inserción bulk"""
    args = b",".join(cur.mogrify("(%s)" % (",".join(["%s"]*len(r))), r) for r in rows)
    cur.execute(template_sql % args.decode())

# ------------------------------------------------------------------------
# 3. Generación e inserción
# ------------------------------------------------------------------------
users_batch, plans_batch, sessions_batch = [], [], []
total = 0

for i in range(5_000):
    # ---- Usuario
    email = faker.unique.email()
    users_batch.append((
        email,
        hash_password(faker.password(length=12)),
        faker.name(),
        faker.image_url(),
        faker.date_time_between(start_date="-2y", end_date="now"),
        faker.date_time_between(start_date="-2y", end_date="now"),
        random.choice([True]*7 + [False]*3),
        random.choice([True]*9 + [False]),
        "free",
        quota := random.choice([5_000, 100_000, 1_000_000]),
        random.randint(0, quota),
    ))

    # ---- Commit por lotes
    if len(users_batch) == BATCH_SIZE or i == 4_999:
        execute_batch(user_sql, users_batch)
        user_ids = [uid for (uid,) in cur.fetchall()]

        for uid in user_ids:
            plan_name, desc, limit, price = random_plan()
            plans_batch.append((uid, plan_name, desc, limit, price, True))

            for _ in range(random.randint(1, 5)):
                created = faker.date_time_between(start_date="-90d", end_date="now")
                expires = created + timedelta(days=random.randint(1, 14))
                sessions_batch.append((
                    uid,
                    expires > datetime.utcnow(),
                    faker.user_agent(),
                    faker.ipv4_public(),
                    created,
                    expires,
                ))

        execute_batch(plan_sql, plans_batch)
        execute_batch(session_sql, sessions_batch)
        conn.commit()

        total += len(user_ids)
        print(f"Lote OK — acumulado {total}")

        users_batch.clear(); plans_batch.clear(); sessions_batch.clear()

cur.close(); conn.close()
print("Carga completada ✔")
