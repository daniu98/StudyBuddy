"""Run the app with: python app.py"""

from studybuddy import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
