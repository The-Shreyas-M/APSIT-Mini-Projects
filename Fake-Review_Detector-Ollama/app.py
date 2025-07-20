from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_review', methods=['POST'])
def check_review():
    data = request.json
    review_text = data.get("prompt", "").strip()

    if not review_text:
        return jsonify({"error": "No review text provided"}), 400

    # Call Ollama API with a simple prompt
    ollama_response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "mistral-nemo:latest", "prompt": review_text, "stream": False}
    )

    if ollama_response.status_code != 200:
        return jsonify({"error": "Ollama API request failed"}), 500

    response_data = ollama_response.json()
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)