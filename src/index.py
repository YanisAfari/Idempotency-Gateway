from .app import app

PORT = 3000

if __name__ == "__main__":
    print(f"Server is listening on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
