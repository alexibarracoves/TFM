const { DatabaseSync } = require('node:sqlite');

// La API solo lee: el recolector de Python es el único que escribe
const db = new DatabaseSync(process.env.DB_PATH || '/app/data/analizador.db', { readOnly: true });
db.exec('PRAGMA busy_timeout = 5000');

// Mantiene la interfaz de pg (query con $1, $2... y resultado en rows)
function query(sql, params = []) {
  const rows = db.prepare(sql.replace(/\$(\d+)/g, '?$1')).all(...params);
  return { rows };
}

module.exports = { query };
