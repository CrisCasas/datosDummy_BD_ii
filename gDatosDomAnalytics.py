#!/usr/bin/env python3
"""
populate_analytics.py   ·   dominio analytics   ·   PostgreSQL ≥ 13

Inserta:
  • 40 000  registros  en file_access_metrics
  • 25 000  registros  en user_usage_metrics
  • 20 000  registros  en sharing_activity_metrics
  •   730   registros  en system_performance_metrics   (2 años, 1/día)
  • 12 000  registros  en tag_usage_metrics

Conexión:
  – POSTGRES_URL  (p.e. postgresql://usr:pwd@host:5432/db?sslmode=require)
  – Ó variables sueltas DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASS
"""

from __future__ import annotations
import os, random, ipaddress, statistics
from datetime import datetime, timedelta, date
from urllib.parse import urlparse, unquote

import psycopg2
from faker import Faker
from dotenv import load_dotenv

# -------------------------------------------------------------- #
# 1. Conexión                                                    #
# -------------------------------------------------------------- #
load_dotenv()
faker = Faker("en_US")
Faker.seed(2025); random.seed(2025)

def build_dsn() -> dict:
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

# -------------------------------------------------------------- #
# 2. Parámetros de volumen                                       #
# -------------------------------------------------------------- #
N_FILE_ACCESS   = 40_000
N_USER_USAGE    = 25_000
N_SHARING       = 20_000
N_SYS_PERF      = 730        # 2 años diarios
N_TAG_USAGE     = 12_000
BATCH_SIZE      = 2_000

USER_RANGE      = (1, 5_000)     # coherente con dominio_usuario
FILE_RANGE      = (1, 20_000)    # coherente con Mongo files
TAG_RANGE       = (1, 100)       # coherente con Mongo tags

START_DATE      = date.today() - timedelta(days=365)   # 1 año atrás
TAG_START       = date.today() - timedelta(days=180)   # 6 meses atrás

# -------------------------------------------------------------- #
# 3. SQL parametrizado                                           #
# -------------------------------------------------------------- #
SQL_FAM = """INSERT INTO file_access_metrics
(file_id, date, view_count, download_count, last_accessed_by_user)
VALUES %s;"""

SQL_UUM = """INSERT INTO user_usage_metrics
(user_id, date, files_uploaded, files_downloaded,
 used_storage_mb, active_minutes, login_count, shared_items_count)
VALUES %s;"""

SQL_SAM = """INSERT INTO sharing_activity_metrics
("timestamp", user_id, date, links_created, shared_files, revoked_links)
VALUES %s;"""

SQL_SPM = """INSERT INTO system_performance_metrics
("timestamp", cpu_usage_percent, disk_io_mb, avg_response_time_ms,
 active_sessions, concurrent_uploads)
VALUES %s;"""

SQL_TUM = """INSERT INTO tag_usage_metrics
(tag_id, date, assigned_to_files, assigned_to_folders, search_hits)
VALUES %s
ON CONFLICT (tag_id, date) DO UPDATE
    SET assigned_to_files    = EXCLUDED.assigned_to_files,
        assigned_to_folders  = EXCLUDED.assigned_to_folders,
        search_hits          = EXCLUDED.search_hits;"""

def exec_batch(sql: str, rows: list[tuple]):
    if not rows:
        return
    args = b",".join(cur.mogrify("(%s)" % (",".join(["%s"]*len(r))), r) for r in rows)
    cur.execute(sql % args.decode())

# -------------------------------------------------------------- #
# 4. Generadores de filas                                        #
# -------------------------------------------------------------- #
def gen_file_access() -> tuple:
    return (
        random.randint(*FILE_RANGE),
        faker.date_between(start_date=START_DATE, end_date="today"),
        random.randint(0, 800),
        random.randint(0, 200),
        random.choice(range(*USER_RANGE)) if random.random() < 0.7 else None
    )

def gen_user_usage() -> tuple:
    files_up = random.randint(0, 20)
    files_dn = random.randint(0, 40)
    return (
        random.randint(*USER_RANGE),
        faker.date_between(start_date=START_DATE, end_date="today"),
        files_up,
        files_dn,
        round(random.uniform(10, 8_000), 2),           # MB
        random.randint(5, 480),                        # minutos activos/día
        random.randint(0, 6),                          # logins/día
        random.randint(0, files_up + files_dn)
    )

def gen_sharing_activity() -> tuple:
    when = faker.date_time_between(start_date="-365d", end_date="now")
    return (
        when,
        uid := random.randint(*USER_RANGE),
        when.date(),
        lnks := random.randint(0, 5),
        shared := random.randint(0, 15),
        random.randint(0, lnks)                        # revoked
    )

def populate_tag_usage(total: int):
    batch_dict, done = {}, 0

    while done < total:
        row = gen_tag_usage()
        key = (row[0], row[1])          # (tag_id, date)

        # Si la clave ya estaba en el lote, acumula contadores
        if key in batch_dict:
            prev = batch_dict[key]
            batch_dict[key] = (
                key[0], key[1],                        # tag_id, date
                prev[2] + row[2],                     # assigned_to_files
                prev[3] + row[3],                     # assigned_to_folders
                prev[4] + row[4]                      # search_hits
            )
        else:
            batch_dict[key] = row

        # ¿Estamos listos para enviar?
        if len(batch_dict) == BATCH_SIZE or done + len(batch_dict) == total:
            exec_batch(SQL_TUM, list(batch_dict.values()))
            done += len(batch_dict)
            conn.commit()
            print(f"tag_usage_metrics: {done}/{total}")
            batch_dict.clear()

def gen_sys_perf(day_index: int) -> tuple:
    ts = datetime.combine(date.today() - timedelta(days=day_index), datetime.min.time())
    cpu = round(random.gauss(mu=42, sigma=15), 2)
    return (
        ts,
        max(0, min(cpu, 99.99)),                       # cpu_usage_percent
        round(abs(random.gauss(500, 200)), 2),         # disk_io_mb
        abs(int(random.gauss(120, 40))),               # avg_response_time_ms
        abs(int(random.gauss(350, 150))),              # active_sessions
        abs(int(random.gauss(80, 40)))                 # concurrent_uploads
    )

def gen_tag_usage() -> tuple:
    return (
        random.randint(*TAG_RANGE),
        faker.date_between(start_date=TAG_START, end_date="today"),
        random.randint(0, 50),
        random.randint(0, 20),
        random.randint(0, 120)
    )
# justo antes del bucle populate
used_fam_keys = set()

def gen_file_access() -> tuple:
    while True:
        fid  = random.randint(*FILE_RANGE)
        d    = faker.date_between(start_date=START_DATE, end_date="today")
        key  = (fid, d)
        if key not in used_fam_keys:
            used_fam_keys.add(key)
            break
    return (
        fid,
        d,
        random.randint(0, 800),
        random.randint(0, 200),
        random.choice(range(*USER_RANGE)) if random.random() < 0.7 else None
    )

# -------------------------------------------------------------- #
# 5. Poblar tablas                                               #
# -------------------------------------------------------------- #
def populate(total: int, builder, sql: str, label: str):
    batch, done = [], 0
    while done < total:
        batch.append(builder())
        if len(batch) == BATCH_SIZE or done + len(batch) == total:
            exec_batch(sql, batch)
            done += len(batch)
            conn.commit()
            print(f"{label}: {done}/{total}")
            batch.clear()

populate(N_FILE_ACCESS, gen_file_access, SQL_FAM, "file_access_metrics")
populate(N_USER_USAGE,  gen_user_usage,  SQL_UUM, "user_usage_metrics")
populate(N_SHARING,     gen_sharing_activity, SQL_SAM, "sharing_activity_metrics")

# system_performance_metrics → una inserción año‐día a día
perf_rows = [gen_sys_perf(i) for i in range(N_SYS_PERF)]
exec_batch(SQL_SPM, perf_rows); conn.commit()
print(f"system_performance_metrics: {len(perf_rows)} insertados")

populate_tag_usage(N_TAG_USAGE)

cur.close(); conn.close()
print("Carga completada ✔")
