import os
from flask import Flask, render_template

# Create the Flask app
app = Flask(__name__)

# Define the home route
@app.route("/")
def home():
    # Render the main system page (ensure `templates/index.html` exists)
    return render_template("index.html")

# Additional routes for your system
@app.route("/login")
def login():
    # Render the login page (ensure `templates/login.html` exists)
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    # Render the dashboard page (ensure `templates/dashboard.html` exists)
    return render_template("dashboard.html")

# Run the app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
