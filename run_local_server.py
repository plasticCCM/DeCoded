import sys

sys.path.insert(0, r".venv\Lib\site-packages")

from app import app


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
