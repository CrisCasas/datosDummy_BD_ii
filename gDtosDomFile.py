#!/usr/bin/env python3
"""
populate_mongo.py  –  FileManagement

● Base de datos   : FileManagement
● Colecciones     : files, folders, tags   (names are case-sensitive)
● Volúmenes       : 100 tags · 5 000 folders · 20 000 files
● Credenciales    : lee la primera URL Mongo válida en
                    MONGO_URL, MONGO_URI o DATABASE_URL
"""

from __future__ import annotations
import os, random
from datetime import datetime, timedelta
from urllib.parse import urlparse
from bson import ObjectId
from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient, InsertOne

# --------------------------------------------------------- #
# 1. Cargar variables de entorno y determinar DSN           #
# --------------------------------------------------------- #
load_dotenv()

def mongo_dsn() -> str:
    for var in ("MONGO_URL", "MONGO_URI", "DATABASE_URL"):
        uri = os.getenv(var)
        if uri and urlparse(uri).scheme.startswith("mongodb"):
            return uri
    raise RuntimeError("No se encontró una URL MongoDB en MONGO_URL / MONGO_URI / DATABASE_URL")

client = MongoClient(mongo_dsn(), serverSelectionTimeoutMS=10_000)
db = client["FileManagement"]  # nombre exacto de la base

files_col   = db["files"]      # nombres exactos
folders_col = db["folders"]
tags_col    = db["tags"]

# --------------------------------------------------------- #
# 2. Parámetros de datos                                    #
# --------------------------------------------------------- #
faker = Faker("en_US")
Faker.seed(2025); random.seed(2025)

NUM_TAGS    = 100
NUM_FOLDERS = 5_000
NUM_FILES   = 20_000
USER_POOL   = [f"user{n:03d}" for n in range(1, 401)]  # 400 usuarios
now = datetime.utcnow()

# --------------------------------------------------------- #
# 3. Tags                                                   #
# --------------------------------------------------------- #
tag_docs, tag_list = [], []
for _ in range(NUM_TAGS):
    tag_id = ObjectId()
    name   = faker.unique.word()
    tag_list.append((tag_id, name))
    tag_docs.append(InsertOne({
        "_id": tag_id,
        "tag_name": name,
        "created_by": random.choice(USER_POOL),
        "created_at": now - timedelta(days=random.randint(0, 730)),
    }))
tags_col.bulk_write(tag_docs)
print(f"Tags insertados: {NUM_TAGS}")

# --------------------------------------------------------- #
# 4. Folders                                                #
# --------------------------------------------------------- #
folder_docs, folder_ids = [], []
for _ in range(NUM_FOLDERS):
    fid = ObjectId()
    folder_ids.append(str(fid))
    created_at = now - timedelta(days=random.randint(0, 730))
    folder_docs.append(InsertOne({
        "_id": fid,
        "owner_id": random.choice(USER_POOL),
        "name": faker.word().capitalize(),
        "parent_folder_id": random.choice(folder_ids) if folder_ids and random.random() < 0.7 else "0",
        "created_at": created_at,
        "last_modified": created_at + timedelta(days=random.randint(0, 30)),
        "is_deleted": False,
        "tags": random.sample([t for _, t in tag_list], k=random.randint(0, 3)),
        "is_public": random.random() < 0.05,
        "shared_with": random.sample(USER_POOL, k=random.randint(0, 4)),
        "has_active_link": random.random() < 0.10,
        "access_count": random.randint(0, 200),
        "last_accessed_at": created_at + timedelta(days=random.randint(0, 60)),
    }))
for i in range(0, NUM_FOLDERS, 1_000):
    folders_col.bulk_write(folder_docs[i:i+1_000])
print(f"Folders insertados: {NUM_FOLDERS}")

# --------------------------------------------------------- #
# 5. Files                                                  #
# --------------------------------------------------------- #
MIME_TYPES = [
    ("application/pdf", ".pdf"),
    ("image/jpeg", ".jpg"),
    ("text/plain", ".txt"),
    ("application/vnd.ms-excel", ".xls"),
    ("application/zip", ".zip"),
]
files_bulk, total, batch = [], 0, 2_000

for _ in range(NUM_FILES):
    mime, ext = random.choice(MIME_TYPES)
    created_at = now - timedelta(days=random.randint(0, 730))
    files_bulk.append(InsertOne({
        "_id": ObjectId(),
        "owner_id": random.choice(USER_POOL),
        "file_name": faker.word() + str(faker.random_number(3)) + ext,
        "parent_folder_id": random.choice(folder_ids),
        "size": random.randint(10_000, 10_000_000),   # bytes
        "mime_type": mime,
        "created_at": created_at,
        "last_modified": created_at + timedelta(days=random.randint(0, 90)),
        "is_deleted": False,
        "tags": random.sample([t for _, t in tag_list], k=random.randint(0, 4)),
        "version": random.randint(1, 10),
        "checksum": faker.md5(raw_output=False),
        "encryption_key": faker.sha1(),
        "is_public": random.random() < 0.04,
        "shared_with": random.sample(USER_POOL, k=random.randint(0, 6)),
        "has_active_link": random.random() < 0.15,
        "download_count": random.randint(0, 1_000),
        "view_count": random.randint(0, 2_000),
        "last_accessed_at": created_at + timedelta(days=random.randint(0, 90)),
        "last_accessed_by": random.choice(USER_POOL),
    }))
    if len(files_bulk) == batch:
        files_col.bulk_write(files_bulk)
        total += len(files_bulk)
        print(f"Files insertados: {total}")
        files_bulk.clear()

if files_bulk:
    files_col.bulk_write(files_bulk)
    total += len(files_bulk)
    print(f"Files insertados: {total}")

print("Carga completada ✔")
client.close()
