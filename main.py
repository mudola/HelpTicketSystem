import os
from flask import Flask

# Create the Flask app
app = Flask(__name__)

# Define a route
@app.route("/")
def home():
    return "Hello, Render!"

# Run the app
if __name__ == "__main__":
    # Use the port provided by Render or default to 8000 for local testing
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
