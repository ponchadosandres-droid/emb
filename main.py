"""
Servidor de conversión EMB → JSON para Visor DST Pro
Convierte archivos .EMB de Wilcom a JSON con datos de puntadas
Compatible con Google Cloud Run, Railway, Render, etc.
"""

import os
import json
import tempfile
from flask import Flask, request, jsonify
import pyembroidery

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "service": "emb-converter",
        "message": "Servidor EMB/DST funcionando 🔥",
        "endpoints": {
            "health": "/health",
            "convert": "/convert (POST)"
        }
    })

# Límite de 10MB para archivos EMB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024


def pattern_to_json(pattern):
    """Convierte un patrón pyembroidery a JSON con capas por color."""
    
    # Comandos de pyembroidery
    STITCH  = pyembroidery.STITCH
    JUMP    = pyembroidery.JUMP
    COLOR_CHANGE = pyembroidery.COLOR_CHANGE
    END     = pyembroidery.END
    TRIM    = pyembroidery.TRIM

    layers = []
    current_layer = []
    colors = []

    # Extraer colores del hilo
    if pattern.threadlist:
        for thread in pattern.threadlist:
            r = getattr(thread, 'color', 0)
            if isinstance(r, int):
                # color es un entero 0xRRGGBB
                colors.append({
                    "r": (r >> 16) & 0xFF,
                    "g": (r >> 8) & 0xFF,
                    "b": r & 0xFF,
                })
            else:
                colors.append({"r": 0, "g": 0, "b": 0})
    
    pen_down = False

    for stitch in pattern.stitches:
        x, y, cmd = stitch[0], stitch[1], stitch[2] & 0xF0

        if cmd == COLOR_CHANGE:
            if current_layer:
                layers.append(list(current_layer))
                current_layer = []
            pen_down = False

        elif cmd == END:
            break

        elif cmd == TRIM or cmd == JUMP:
            # Levantar pluma (NaN como separador, igual que en DST)
            current_layer.append({"x": None, "y": None})
            pen_down = False

        elif cmd == STITCH or cmd == 0:
            # Puntada normal - invertir Y igual que en decodeDST
            current_layer.append({"x": float(x), "y": float(-y)})
            pen_down = True

    if current_layer:
        layers.append(current_layer)

    # Calcular bounds
    all_points = [p for layer in layers for p in layer if p["x"] is not None]
    if all_points:
        min_x = min(p["x"] for p in all_points)
        max_x = max(p["x"] for p in all_points)
        min_y = min(p["y"] for p in all_points)
        max_y = max(p["y"] for p in all_points)
    else:
        min_x = max_x = min_y = max_y = 0

    total_stitches = sum(
        1 for layer in layers for p in layer if p["x"] is not None
    )

    return {
        "layers": layers,
        "colors": colors,
        "bounds": {
            "minX": min_x, "maxX": max_x,
            "minY": min_y, "maxY": max_y
        },
        "totalStitches": total_stitches,
        "totalColors": len(layers)
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "emb-converter"})


@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400

    file = request.files["file"]
    filename = file.filename or "design"
    ext = os.path.splitext(filename)[1].lower()

    # Formatos soportados por pyembroidery
    SUPPORTED = {".emb", ".dst", ".pes", ".jef", ".vp3", ".exp",
                 ".hus", ".dat", ".pec", ".xxx", ".sew", ".csd"}

    if ext not in SUPPORTED:
        return jsonify({"error": f"Formato no soportado: {ext}"}), 400

    # Guardar en archivo temporal y leer con pyembroidery
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        file.save(tmp_path)

    try:
        pattern = pyembroidery.read(tmp_path)
        if pattern is None:
            return jsonify({"error": "No se pudo leer el archivo"}), 422

        result = pattern_to_json(pattern)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 500

    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
