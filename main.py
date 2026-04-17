from flask import Flask, request, jsonify
from flask_cors import CORS  # <--- Agregado
import pyembroidery
import tempfile
import os

app = Flask(__name__)
CORS(app)  # <--- Habilita permisos para que la app se conecte

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Servidor EMB/DST funcionando 🔥"
    })

@app.route("/convert", methods=["POST"])
def convert():
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Agregamos esta línea para forzar el cierre manual antes de leer
    tmp.close() 

    try:
        # Ahora pyembroidery lo lee de un archivo que ya está cerrado y libre
        pattern = pyembroidery.read(tmp_path)
        # ... resto del código
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    ext = os.path.splitext(file.filename)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Forzamos la lectura específica
        pattern = pyembroidery.read(tmp_path)

        # Si pattern es None, es que pyembroidery no pudo con esa versión de EMB
        if pattern is None:
            return jsonify({"error": "No se pudo interpretar el archivo EMB. Intenta guardarlo como una versión más antigua en Wilcom (ej. e2 o e3)."}), 400

        layers = []
        current = []

        # Usamos pattern.stitches de forma segura
        stitches = getattr(pattern, 'stitches', [])
        
        if not stitches:
             return jsonify({"error": "El archivo no contiene puntadas procesables."}), 400

        for stitch in stitches:
            x, y, cmd = stitch

            if cmd == pyembroidery.COLOR_CHANGE:
                if current:
                    layers.append(current)
                    current = []
            elif cmd == pyembroidery.STITCH:
                current.append({"x": float(x), "y": float(-y)})
            elif cmd == pyembroidery.JUMP:
                current.append({"x": None, "y": None})

        if current:
            layers.append(current)

        # Filtro de seguridad para los límites
        all_x = [p["x"] for l in layers for p in l if p["x"] is not None]
        all_y = [p["y"] for l in layers for p in l if p["y"] is not None]

        if not all_x or not all_y:
            return jsonify({"error": "Diseño vacío o sin coordenadas válidas."}), 400

        return jsonify({
            "layers": layers,
            "colors": [],
            "bounds": {
                "minX": min(all_x),
                "minY": min(all_y),
                "maxX": max(all_x),
                "maxY": max(all_y)
            },
            "totalStitches": sum(len(l) for l in layers)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    # Importante: Render usa la variable PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)