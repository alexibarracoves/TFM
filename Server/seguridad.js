const crypto = require('crypto');

const TOKEN = process.env.ANALIZADOR_TOKEN || '';
const COOKIE = 'analizador_token';

const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'"
].join('; ');

function cabeceras(req, res, next) {
  res.set({
    'Content-Security-Policy': CSP,
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin'
  });
  next();
}

function tokenValido(valor) {
  if (typeof valor !== 'string' || !valor) return false;
  const a = crypto.createHash('sha256').update(valor).digest();
  const b = crypto.createHash('sha256').update(TOKEN).digest();
  return crypto.timingSafeEqual(a, b);
}

function leerCookie(req, nombre) {
  for (const parte of (req.headers.cookie || '').split(';')) {
    const [clave, ...valor] = parte.trim().split('=');
    if (clave === nombre) return decodeURIComponent(valor.join('='));
  }
  return null;
}

// Si ANALIZADOR_TOKEN está definido, se exige en todas las rutas salvo /salud.
// Se acepta como cabecera "Authorization: Bearer <token>" o, desde el navegador,
// abriendo una vez la URL con ?token=<token>, que lo guarda en una cookie HttpOnly.
function autenticacion(req, res, next) {
  if (!TOKEN || req.path === '/salud') return next();

  if (tokenValido(req.query.token)) {
    res.cookie(COOKIE, req.query.token, { httpOnly: true, sameSite: 'strict', path: '/' });
    const url = new URL(req.originalUrl, 'http://localhost');
    url.searchParams.delete('token');
    return res.redirect(303, url.pathname + url.search);
  }

  const cabecera = req.get('authorization') || '';
  const bearer = cabecera.startsWith('Bearer ') ? cabecera.slice(7) : null;
  if (tokenValido(bearer) || tokenValido(leerCookie(req, COOKIE))) return next();

  if (req.accepts(['json', 'html']) === 'html') {
    return res.status(401).type('html').send(
      '<!doctype html><meta charset="utf-8"><title>Acceso restringido</title>' +
      '<p>Este analizador requiere un token. Abre la dirección con <code>?token=&lt;tu token&gt;</code>.</p>'
    );
  }
  res.status(401).json({ error: 'Token de acceso requerido' });
}

module.exports = { cabeceras, autenticacion, activo: Boolean(TOKEN) };
