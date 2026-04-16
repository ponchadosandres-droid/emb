from flask import Flask, request, jsonify
import pyembroidery
import tempfile
import os

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Servidor EMB/DST funcionando 🔥"
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

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

            elif cmd == pyembroidery.STITCH:
                current.append({"x": float(x), "y": float(-y)})

        if current:
            layers.append(current)

        return jsonify({
            "layers": layers,
            "colors": [],
            "bounds": {
                "minX": 0,
                "minY": 0,
                "maxX": 0,
                "maxY": 0
            },
            "totalStitches": sum(len(l) for l in layers)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        os.remove(tmp_path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)