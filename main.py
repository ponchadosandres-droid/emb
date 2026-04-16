"""
Servidor de conversión EMB → JSON para Visor DST Pro
"""
import os
import json
import tempfile
from flask import Flask, request, jsonify
import pyembroidery

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

def pattern_to_json(pattern):
    """
    Convierte un patrón pyembroidery a JSON con capas por color.

    UNIDADES: pyembroidery usa décimas de milímetro (0.1mm = 1 unidad),
    igual que DST Tajima. No se necesita escalar.
    """
    STITCH       = pyembroidery.STITCH
    JUMP         = pyembroidery.JUMP
    COLOR_CHANGE = pyembroidery.COLOR_CHANGE
    TRIM         = pyembroidery.TRIM
    END          = pyembroidery.END
    SEQUENCE_BREAK = pyembroidery.SEQUENCE_BREAK

    layers  = []
    colors  = []
    current = []

    # ---- Extraer colores ----
    if pattern.threadlist:
        for thread in pattern.threadlist:
            c = getattr(thread, 'color', 0)
            if isinstance(c, int):
                colors.append({
                    "r": (c >> 16) & 0xFF,
                    "g": (c >> 8)  & 0xFF,
                    "b":  c        & 0xFF,
                })
            else:
                colors.append({"r": 0, "g": 0, "b": 0})

    # ---- Recorrer puntadas ----
    for stitch in pattern.stitches:
        x   = stitch[0]
        y   = stitch[1]
        cmd = stitch[2] & pyembroidery.COMMAND_MASK   # solo bits de comando

        if cmd in (COLOR_CHANGE, SEQUENCE_BREAK):
            if current:
                layers.append(list(current))
                current = []
            # Separador de pluma también al inicio de la nueva capa
            current.append({"x": None, "y": None})

        elif cmd == END:
            break

        elif cmd in (TRIM, JUMP):
            # Levantar pluma → separador NaN equivalente al DST
            current.append({"x": None, "y": None})

        else:
            # STITCH normal.
            # pyembroidery usa décimas de mm, igual que DST.
            # Invertir Y para que coincida con la convención del visor.
            current.append({"x": float(x), "y": float(-y)})

    if current:
        layers.append(current)

    # Eliminar capas vacías o con solo separadores
    layers = [
        layer for layer in layers
        if any(p["x"] is not None for p in layer)
    ]

    # ---- Calcular bounds ----
    all_pts = [p for layer in layers for p in layer if p["x"] is not None]
    if all_pts:
        min_x = min(p["x"] for p in all_pts)
        max_x = max(p["x"] for p in all_pts)
        min_y = min(p["y"] for p in all_pts)
        max_y = max(p["y"] for p in all_pts)
    else:
        min_x = max_x = min_y = max_y = 0.0

    total_stitches = len(all_pts)

    # Ajustar lista de colores para que coincida con número de capas
    while len(colors) < len(layers):
        colors.append({"r": 0, "g": 0, "b": 0})
    colors = colors[:len(layers)]

    return {
        "layers":        layers,
        "colors":        colors,
        "bounds":        {"minX": min_x, "maxX": max_x,
                          "minY": min_y, "maxY": max_y},
        "totalStitches": total_stitches,
        "totalColors":   len(layers),
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "emb-converter"})


@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400

    file     = request.files["file"]
    filename = file.filename or "design"
    ext      = os.path.splitext(filename)[1].lower()

    SUPPORTED = {
        ".emb", ".dst", ".pes", ".jef", ".vp3",
        ".exp", ".hus", ".dat", ".xxx", ".sew", ".csd",
    }

    if ext not in SUPPORTED:
        return jsonify({"error": f"Formato no soportado: {ext}"}), 400

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
        except Exception:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
