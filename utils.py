import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from datetime import date

DATA_DIR = 'data'
CHART_DIR = 'static/charts'
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

def load_csv_safely(file_path, expected_columns):
    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=expected_columns)
        df.to_csv(file_path, index=False)
        return df
    try:
        df = pd.read_csv(file_path)
        for col in expected_columns:
            if col not in df.columns:
                df[col] = ''
        return df
    except Exception:
        df = pd.DataFrame(columns=expected_columns)
        df.to_csv(file_path, index=False)
        return df

def log_activity(activity_type, description):
    logs_path = os.path.join(DATA_DIR, 'activity_logs.csv')
    df_logs = load_csv_safely(logs_path, ['id', 'date', 'activity_type', 'description'])
    
    import uuid
    new_id = str(uuid.uuid4())[:8]
    today_str = date.today().strftime('%Y-%m-%d')
    
    new_row = pd.DataFrame([{
        'id': new_id,
        'date': today_str,
        'activity_type': str(activity_type),
        'description': str(description)
    }])
    
    df_logs = pd.concat([df_logs, new_row], ignore_index=True)
    df_logs.to_csv(logs_path, index=False)

def ensure_files():
    files = {
        'transactions.csv': ['id', 'date', 'type', 'title', 'amount', 'category'],
        'categories.csv': ['id', 'name', 'type'],
        'assets.csv': ['id', 'date', 'name', 'value', 'type', 'status'],
        'goals.csv': ['id', 'title', 'target_amount', 'current_amount', 'deadline'],
        'budgets.csv': ['id', 'category', 'monthly_limit']
    }
    for filename, headers in files.items():
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            df = pd.DataFrame(columns=headers)
            df.to_csv(filepath, index=False)

def generate_charts(df_trans, df_assets):
    # 1. Income vs Expense Comparison Pie Chart
    plt.figure(figsize=(5, 3))
    if not df_trans.empty and 'type' in df_trans.columns and 'amount' in df_trans.columns:
        summary = df_trans.groupby('type')['amount'].sum()
        if not summary.empty:
            summary.plot(kind='pie', autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
    plt.title('Income vs Expense Comparison')
    plt.ylabel('')
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, 'income_expense_pie.png'))
    plt.close()

    # 2. Expense Breakdown by Category
    plt.figure(figsize=(6, 3))
    if not df_trans.empty and 'type' in df_trans.columns and 'category' in df_trans.columns:
        df_expenses = df_trans[df_trans['type'].str.lower() == 'expense']
        if not df_expenses.empty:
            cat_summary = df_expenses.groupby('category')['amount'].sum()
            cat_summary.plot(kind='bar', color='#e74c3c')
        else:
            pd.Series([0], index=['No Expenses']).plot(kind='bar', color='#bdc3c7')
    plt.title('Expense Breakdown by Category')
    plt.ylabel('Amount')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, 'expense_by_category.png'))
    plt.close()

    # 3. Asset Distribution Pie Chart
    plt.figure(figsize=(5, 3))
    if not df_assets.empty and 'value' in df_assets.columns:
        df_assets['value'] = pd.to_numeric(df_assets['value'], errors='coerce')
        df_assets.groupby('type')['value'].sum().plot(kind='pie', autopct='%1.1f%%', startangle=140)
    plt.title('Asset Distribution')
    plt.ylabel('')
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, 'assets_pie.png'))
    plt.close()