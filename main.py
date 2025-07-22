
from app import app

# Import routes to register them with the app
import routes

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
