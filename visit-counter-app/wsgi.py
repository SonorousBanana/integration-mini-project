import os

from counter import create_app

app = create_app()

if __name__ == "__main__":
    # Dev server only. In containers use: gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
