CREATE DATABASE contenedores;
\c contenedores;

CREATE TABLE IF NOT EXISTS imagenes (
    id SERIAL PRIMARY KEY,
    nombre TEXT UNIQUE,
    hash TEXT UNIQUE,
    numero_desconocida INT,
    numero_baja INT,
    numero_media INT,
    numero_alta INT,
    numero_critica INT
);

CREATE TABLE IF NOT EXISTS contenedores (
    id SERIAL PRIMARY KEY,
    nombre TEXT,
    estado TEXT,
    imagen_id INT REFERENCES imagenes(id) ON DELETE CASCADE,
    capacidades TEXT,
    puertos JSONB,
    interfaces JSONB
);

CREATE TABLE IF NOT EXISTS vulnerabilidades (
    id SERIAL PRIMARY KEY,
    imagen_id INT REFERENCES imagenes(id) ON DELETE CASCADE,
    vulnerabilidad TEXT,
    libreria TEXT,
    severidad TEXT,
    estado TEXT,
    version TEXT,
    informacion TEXT,
    enlace TEXT
);

CREATE TABLE IF NOT EXISTS podman (
    id SERIAL PRIMARY KEY,
    modo_root BOOLEAN NOT NULL
);