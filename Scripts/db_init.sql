CREATE TABLE IF NOT EXISTS imagenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE,
    hash TEXT UNIQUE,
    numero_desconocida INTEGER,
    numero_baja INTEGER,
    numero_media INTEGER,
    numero_alta INTEGER,
    numero_critica INTEGER,
    estado_escaneo TEXT NOT NULL DEFAULT 'pendiente',
    detalle_escaneo TEXT,
    fecha_escaneo TEXT
);

CREATE TABLE IF NOT EXISTS contenedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    estado TEXT,
    imagen_id INTEGER REFERENCES imagenes(id) ON DELETE CASCADE,
    capacidades TEXT,
    puertos TEXT,
    interfaces TEXT
);

CREATE TABLE IF NOT EXISTS vulnerabilidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imagen_id INTEGER REFERENCES imagenes(id) ON DELETE CASCADE,
    vulnerabilidad TEXT,
    libreria TEXT,
    severidad TEXT,
    estado TEXT,
    version TEXT,
    informacion TEXT,
    enlace TEXT
);

CREATE INDEX IF NOT EXISTS idx_vulnerabilidades_imagen ON vulnerabilidades (imagen_id);

CREATE TABLE IF NOT EXISTS motor (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    modo_root INTEGER NOT NULL
);
