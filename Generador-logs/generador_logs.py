#!/usr/bin/env python3
import random
import time
from datetime import datetime

# Niveles de log y sus probabilidades
niveles = ['INFO', 'DEBUG', 'WARNING', 'ERROR']
pesos   = [0.50,   0.25,    0.20,      0.05]  

# Mensajes de ejemplo por nivel
mensajes = {
    'INFO':    ['Arrancando servicio', 'Operación completada', 'Pong'],
    'DEBUG':   ['Variable x=42', 'Payload recibido', 'Contexto interno'],
    'WARNING': ['Uso de memoria alto', 'Retardo en respuesta', 'SSL sin verificar'],
    'ERROR':   ['Conexión rechazada', 'Excepción no controlada', 'Fallo crítico']
}

# Eventos poco frecuentes (anomalías reales que el análisis debería detectar)
EVENTO_RARO_PROB = 0.003
eventos_raros = [
    lambda: ('WARNING', f"Intento de acceso denegado para el usuario admin desde 10.0.{random.randint(0, 255)}.{random.randint(1, 254)}"),
    lambda: ('ERROR', f"El proceso worker-{random.randint(1, 8)} terminó inesperadamente (señal 9)"),
    lambda: ('CRITICAL', "Disco lleno en /var/lib/datos: no se pueden escribir más registros"),
]

# Parámetros para ráfagas (picos) de actividad
BURST_PROB      = 0.10   # 10% de probabilidad de iniciar una ráfaga
BURST_MIN       = 5      # mínimo de logs en ráfaga
BURST_MAX       = 20     # máximo de logs en ráfaga
BURST_SLEEP_MIN = 0.01   # intervalo entre logs en ráfaga, mínimo
BURST_SLEEP_MAX = 0.05   # intervalo entre logs en ráfaga, máximo

# Intervalo normal entre logs
NORMAL_SLEEP_MIN = 0.1
NORMAL_SLEEP_MAX = 1.0

def generar_log():
    """Genera un log con timestamp ISO, nivel y mensaje aleatorio."""
    if random.random() < EVENTO_RARO_PROB:
        nivel, msg = random.choice(eventos_raros)()
    else:
        nivel = random.choices(niveles, pesos)[0]
        msg   = random.choice(mensajes[nivel])
    ts    = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    print(f"{ts} {nivel} {msg}", flush=True)

if __name__ == '__main__':
    try:
        while True:
            if random.random() < BURST_PROB:
                # Iniciar una ráfaga de logs rápida
                burst_size = random.randint(BURST_MIN, BURST_MAX)
                for _ in range(burst_size):
                    generar_log()
                    time.sleep(random.uniform(BURST_SLEEP_MIN, BURST_SLEEP_MAX))
            else:
                # Modo normal de generación de logs
                generar_log()
                time.sleep(random.uniform(NORMAL_SLEEP_MIN, NORMAL_SLEEP_MAX))
    except KeyboardInterrupt:
        print("Generador detenido.")
