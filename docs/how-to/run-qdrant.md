## Prerequisites

- Python 3.10+
- Docker (for Qdrant)

## Start Qdrant (Windows PowerShell)

```bash
mkdir qdrant_embeddings_data


docker run -d -p 6333:6333 -p 6334:6334 -v "%cd%\qdrant_embeddings_data:/qdrant/storage" qdrant/qdrant:latest


```

## Setup API

```bash
python -m venv .venv
. .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Env (optional): `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_MODEL_NAME`, `CHUNK_SIZE`, `CHUNK_OVERLAP`.

## Collections (Organizations)

- Create collection (idempotent):
  - POST `/v1/tenants/collections?collection_name=acme_org_docs`
- All other endpoints require an existing `collection_name`. If it does not exist, they return 404.

## Bulk Upload (Async)

- POST `/v1/documents/upload` (tags: files-upload)
- Form fields (multipart/form-data):
  - `collection_name` (string, required)
  - `files` (one or more files, required) — supports `.pdf`, `.docx`, `.md/.markdown`, `.txt`
- Behavior:
  - Files are parsed → chunked → embedded → upserted in background.
  - Each file creates or increments a version for a deterministic `file_id` derived from filename (`uuid5` of filename) and marks previous chunks (same `file_id`) as `is_current=false`.
  - Each chunk payload includes: `file_id`, `version`, `is_current`, `valid_from`, `valid_until`, `doc_hash`, `chunk_index`, `content`, and `filename`.
- Response: `{ "status": "ok", "message": "files embeddings are being generated. Have a patience" }`.

### Upload Status

- GET `/v1/documents/upload-status?collection_name=<name>` → `{ collection_name, in_progress: true|false }`

## Update Existing File (Replace vs New Version)

- POST `/v1/documents/update-existing-file` (tags: files-upload)
- Form fields (multipart/form-data):
  - `collection_name` (string, required)
  - `file_id` (UUID, required)
  - `is_replace` (bool, required)
  - `file` (file, required; .pdf/.docx/.md/.markdown/.txt)
- Behavior:
  - The filename of the uploaded file is persisted in each chunk payload (`filename`).
  - If `is_replace=true`: delete all existing chunks for `file_id`, then insert new chunks as version `1`, `is_current=true`.
  - If `is_replace=false`: mark previous chunks for `file_id` as `is_current=false` and set `valid_until`; insert new chunks with incremented `version` and `is_current=true`.
  - If the uploaded content is identical and you call the JSON upsert flow elsewhere with `allow_same_content_new_version=false`, duplicates are blocked. In this endpoint we always embed and upsert for the provided file.

## Search

- POST `/v1/search/`
- Body:

```json
{
  "collection_name": "acme_org_docs",
  "file_id": "22222222-2222-2222-2222-222222222222",
  "query": "What is premium price?",
  "top_k": 5
}
```

- Searches only `is_current=true` chunks. Omit `file_id` to search across all files in the collection.

## Notes

- Collections provide strict tenant isolation; data never crosses collections.
- Payload indexes used: `file_id`, `doc_hash`, `version`, `is_current`, `valid_from`, `valid_until`.
- Duplicate detection is based on `doc_hash` (SHA-256 of parsed text) and can be enforced in upsert flows.
