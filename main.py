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
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    ext = os.path.splitext(file.filename)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        pattern = pyembroidery.read(tmp_path)
        layers = []
        current = []

        for stitch in pattern.stitches:
            x, y, cmd = stitch

            if cmd == pyembroidery.COLOR_CHANGE:
                if current:
                    layers.append(current)
                    current = []
            
            # Capturamos puntadas normales
            elif cmd == pyembroidery.STITCH:
                current.append({"x": float(x), "y": float(-y)})
            
            # Capturamos SALTOS (Esto evita que el diseño se vea mal)
            elif cmd == pyembroidery.JUMP:
                current.append({"x": None, "y": None})

        if current:
            layers.append(current)

        # Calculamos los límites reales (Bounds) para que Flutter sepa centrarlo
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
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    # Importante: Render usa la variable PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)