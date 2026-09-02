from flask import Flask
from utils import ensure_files
from routes.main import main_bp
from routes.categories import categories_bp
from routes.transactions import transactions_bp
from routes.assets import assets_bp
from routes.goals import goals_bp
from routes.budgets import budgets_bp

app = Flask(__name__)

# Ensure data and directories exist on startup
ensure_files()

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(categories_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(goals_bp)
app.register_blueprint(budgets_bp)

if __name__ == '__main__':
    app.run(debug=True)