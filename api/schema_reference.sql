
-- Reference schema. The API creates these tables automatically on startup.
-- Use this file for inspection or manual database administration.

CREATE TABLE IF NOT EXISTS import_batches (
    id varchar(36) PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    contributor varchar(120) NOT NULL,
    save_name varchar(200) NOT NULL,
    platform varchar(40) NOT NULL DEFAULT '',
    client_version varchar(80) NOT NULL DEFAULT '',
    source_fingerprint varchar(64) NOT NULL,
    summary jsonb NOT NULL
);
