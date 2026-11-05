const express = require('express');
const path = require('path');
const pool = require('./db');
const seguridad = require('./seguridad');
const { execFile } = require('child_process');
const app = express();
const PORT = 3000;

// Nombres válidos de contenedor en Docker y Podman
const NOMBRE_CONTENEDOR = /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,254}$/;
const MAX_ANALISIS_LOGS = 2;
let analisisEnCurso = 0;

function paginacion(query) {
  const page = Math.max(parseInt(query.page) || 0, 0);
  const size = Math.min(Math.max(parseInt(query.size) || 5, 1), 100);
  return { page, size, offset: page * size };
}

app.disable('x-powered-by');
app.use(seguridad.cabeceras);
app.use(seguridad.autenticacion);

app.use(express.static(path.join(__dirname, 'public')));

app.get('/contenedores', async (req, res) => {
  try {
    const { size, offset } = paginacion(req.query);

    const dataQuery = await pool.query(`
      SELECT c.id, c.nombre, c.estado, i.id as imagen_id, i.nombre AS imagen_nombre, c.capacidades, c.puertos, c.interfaces
      FROM contenedores c
      LEFT JOIN imagenes i ON c.imagen_id = i.id
      ORDER BY c.id
      LIMIT $1 OFFSET $2
    `, [size, offset]);

    const countQuery = await pool.query(`
      SELECT COUNT(*) AS count FROM contenedores
    `);

    const motorQuery = await pool.query(`
      SELECT nombre, modo_root FROM motor LIMIT 1
    `);
    const motor = motorQuery.rows.length > 0 ? motorQuery.rows[0] : null;

    const totalItems = parseInt(countQuery.rows[0].count);
    const totalPages = Math.ceil(totalItems / size);

    res.json({
      data: dataQuery.rows.map(c => ({ ...c, puertos: JSON.parse(c.puertos), interfaces: JSON.parse(c.interfaces) })),
      totalPages,
      totalItems,
      motor: motor ? motor.nombre : null,
      modo: motor ? (motor.modo_root ? 'root' : 'rootless') : null
    });

  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

app.get('/vulnerabilidades/:idImagen', async (req, res) => {
  try {
    const { idImagen } = req.params;
    const { size, offset } = paginacion(req.query);

    const dataQuery = await pool.query(`
      SELECT v.vulnerabilidad, v.libreria, v.severidad, v.estado, v.version, v.informacion, v.enlace
      FROM vulnerabilidades v
      WHERE v.imagen_id = $1
      ORDER BY v.id
      LIMIT $2 OFFSET $3
    `, [idImagen, size, offset]);

    const countQuery = await pool.query(`
      SELECT COUNT(*) AS total
      FROM vulnerabilidades v
      WHERE v.imagen_id = $1
    `, [idImagen]);

    const totalItems = parseInt(countQuery.rows[0].total);
    const totalPages = Math.ceil(totalItems / size);

    res.json({
      data: dataQuery.rows,
      totalPages,
      totalItems
    });

  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

app.get('/imagenes/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const imageQuery = await pool.query(`
      SELECT id, nombre, hash, numero_desconocida, numero_baja, numero_media, numero_alta, numero_critica,
             estado_escaneo, detalle_escaneo, fecha_escaneo
      FROM imagenes
      WHERE id = $1
    `, [id]);

    if (imageQuery.rows.length === 0) {
      return res.status(404).json({ error: 'Imagen no encontrada' });
    }

    res.json(imageQuery.rows[0]);
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

app.get('/contenedores/:nombre/logs/resumen', async (req, res) => {
  const { nombre } = req.params;

  const numLineas = 10000;

  // Solo se analizan contenedores que el recolector tiene registrados
  if (!NOMBRE_CONTENEDOR.test(nombre) || pool.query('SELECT 1 FROM contenedores WHERE nombre = $1', [nombre]).rows.length === 0) {
    return res.status(404).json({ resumen: 'Contenedor no encontrado.' });
  }
  if (analisisEnCurso >= MAX_ANALISIS_LOGS) {
    return res.status(429).json({ resumen: 'Hay demasiados análisis en curso. Inténtalo de nuevo en unos segundos.' });
  }
  analisisEnCurso++;

  const opciones = { cwd: __dirname, timeout: 120000, maxBuffer: 32 * 1024 * 1024 };
  execFile('python3', ['../Scripts/analisis_logs.py', nombre, numLineas], opciones, (error, stdout, stderr) => {
    analisisEnCurso--;
    if (error) {
      console.error('Error ejecutando el script de análisis:', error);
      return res.status(500).json({ resumen: 'Error al analizar los logs.' });
    }
    if (stderr) {
      console.error('Stderr del script:', stderr);
    }

    res.json({ resumen: stdout.trim() });
  });
});

app.get('/salud', (req, res) => {
  try {
    pool.query('SELECT 1');
    res.json({ estado: 'ok' });
  } catch (error) {
    res.status(503).json({ estado: 'error' });
  }
});

app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Servidor escuchando en puerto ${PORT}`);
  if (!seguridad.activo) {
    console.log('AVISO: la API no tiene token de acceso. Publica el puerto solo en 127.0.0.1 o define ANALIZADOR_TOKEN.');
  }
});