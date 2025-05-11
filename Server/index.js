const express = require('express');
const pool = require('./db');
const cors = require('cors');
const { execFile } = require('child_process');
const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

app.get('/contenedores', async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 0;
    const size = parseInt(req.query.size) || 5;

    const offset = page * size;

    const dataQuery = await pool.query(`
      SELECT c.id, c.nombre, c.estado, i.id as imagen_id, i.nombre AS imagen_nombre, c.capacidades, c.puertos, c.interfaces
      FROM contenedores c
      LEFT JOIN imagenes i ON c.imagen_id = i.id
      ORDER BY c.id
      LIMIT $1 OFFSET $2
    `, [size, offset]);

    const countQuery = await pool.query(`
      SELECT COUNT(*) FROM contenedores
    `);

    const podmanQuery = await pool.query(`
      SELECT modo_root FROM podman LIMIT 1
    `);
    const modoRoot = podmanQuery.rows.length > 0 ? podmanQuery.rows[0].modo_root : null;

    const totalItems = parseInt(countQuery.rows[0].count);
    const totalPages = Math.ceil(totalItems / size);

    res.json({
      data: dataQuery.rows,
      totalPages,
      totalItems,
      podmanMode: modoRoot ? 'root' : 'rootless'
    });

  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

app.get('/vulnerabilidades/:idImagen', async (req, res) => {
  try {
    const { idImagen } = req.params;
    const page = parseInt(req.query.page) || 0;
    const size = parseInt(req.query.size) || 5;
    const offset = page * size;

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
      SELECT id, nombre, hash, numero_desconocida, numero_baja, numero_media, numero_alta, numero_critica
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

  const numLineas = 1000;

  execFile('python3', ['../Scripts/analisis_logs.py', nombre, numLineas], { cwd: __dirname }, (error, stdout, stderr) => {
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

app.listen(PORT, () => {
  console.log(`Servidor escuchando en puerto ${PORT}`);
});