from flask import Flask, request, jsonify
from flask_cors import CORS
import pyembroidery
import tempfile
import os

app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Servidor Ponchados Andres funcionando 🔥"
    })

@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No hay archivo en la peticion"}), 400

    file = request.files["file"]
    ext = os.path.splitext(file.filename)[1].lower()

    # Creamos el archivo temporal
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        file.save(tmp.name)
        tmp_path = tmp.name
        tmp.close() # Lo cerramos para que pyembroidery pueda leerlo sin bloqueos

        pattern = pyembroidery.read(tmp_path)

        if pattern is None:
            return jsonify({"error": "Wilcom version no soportada. Guarda como EMB e3."}), 400

        layers = []
        current = []
        
        # Acceso seguro a las puntadas
        stitches = getattr(pattern, "stitches", [])

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

        if not layers:
            return jsonify({"error": "El archivo no tiene puntadas"}), 400

        # Calculo de limites para el centrado en Flutter
        all_x = [p["x"] for l in layers for p in l if p["x"] is not None]
        all_y = [p["y"] for l in layers for p in l if p["y"] is not None]

        return jsonify({
            "layers": layers,
            "colors": [],
            "bounds": {
                "minX": min(all_x) if all_x else 0,
                "minY": min(all_y) if all_y else 0,
                "maxX": max(all_x) if all_x else 0,
                "maxY": max(all_y) if all_y else 0
            },
            "totalStitches": sum(len(l) for l in layers)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)