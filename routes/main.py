from datetime import date, timedelta
import os
import pandas as pd
from flask import Blueprint, render_template, request, Response
from utils import DATA_DIR, load_csv_safely, generate_charts

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    trans_path = os.path.join(DATA_DIR, 'transactions.csv')
    assets_path = os.path.join(DATA_DIR, 'assets.csv')
    goals_path = os.path.join(DATA_DIR, 'goals.csv')
    budgets_path = os.path.join(DATA_DIR, 'budgets.csv')

    df_trans = load_csv_safely(trans_path, ['id', 'date', 'type', 'title', 'amount', 'category'])
    df_assets = load_csv_safely(assets_path, ['id', 'date', 'name', 'value', 'type', 'status'])
    df_goals = load_csv_safely(goals_path, ['id', 'title', 'target_amount', 'current_amount', 'deadline'])
    df_budgets = load_csv_safely(budgets_path, ['id', 'category', 'limit'])

    # Determine correct limit column name in budgets.csv
    limit_col = 'limit' if 'limit' in df_budgets.columns else 'monthly_limit'

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Filter transactions and calculate budget spent map based on custom dates or current month
    df_trans_filtered = df_trans.copy()
    spent_map = {}

    if not df_trans_filtered.empty and 'date' in df_trans_filtered.columns and 'amount' in df_trans_filtered.columns:
        df_trans_filtered['date_dt'] = pd.to_datetime(df_trans_filtered['date'], errors='coerce')
        df_trans_filtered['amount_num'] = pd.to_numeric(df_trans_filtered['amount'], errors='coerce').fillna(0)

        # Use custom date range if selected, otherwise default to current month for budgets
        if start_date or end_date:
            df_date_filtered = df_trans_filtered.copy()
            if start_date:
                df_date_filtered = df_date_filtered[df_date_filtered['date_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_date_filtered = df_date_filtered[df_date_filtered['date_dt'] <= pd.to_datetime(end_date)]
            
            exp_calc = df_date_filtered[df_date_filtered['type'].str.lower() == 'expense']
        else:
            current_year_month = date.today().strftime('%Y-%m')
            exp_calc = df_trans_filtered[
                (df_trans_filtered['date_dt'].dt.strftime('%Y-%m') == current_year_month) & 
                (df_trans_filtered['type'].str.lower() == 'expense')
            ]

        if not exp_calc.empty:
            spent_map = exp_calc.groupby('category')['amount_num'].sum().to_dict()

        # General transaction date filtering for dashboard cards
        if start_date:
            df_trans_filtered = df_trans_filtered[df_trans_filtered['date_dt'] >= pd.to_datetime(start_date)]
        if end_date:
            df_trans_filtered = df_trans_filtered[df_trans_filtered['date_dt'] <= pd.to_datetime(end_date)]
        df_trans_filtered = df_trans_filtered.drop(columns=['date_dt'], errors='ignore')

    total_transactions = len(df_trans_filtered) if not df_trans_filtered.empty else 0
    total_income = 0.0
    total_expense = 0.0

    incomes = []
    expenses = []

    if not df_trans_filtered.empty:
        inc_df = df_trans_filtered[df_trans_filtered['type'].str.lower() == 'income']
        exp_df = df_trans_filtered[df_trans_filtered['type'].str.lower() == 'expense']

        total_income = inc_df['amount_num'].sum()
        total_expense = exp_df['amount_num'].sum()

        incomes = inc_df.to_dict(orient='records')
        expenses = exp_df.to_dict(orient='records')

    net_balance = total_income - total_expense

    # Assets calculation
    total_assets = 0.0
    assets_active = []
    all_assets = []
    if not df_assets.empty:
        if 'status' not in df_assets.columns:
            df_assets['status'] = 'active'
        else:
            df_assets['status'] = df_assets['status'].fillna('active')
        all_assets = df_assets.to_dict(orient='records')
        active_df = df_assets[df_assets['status'].str.lower() == 'active'].copy()
        if not active_df.empty:
            active_df['val_num'] = pd.to_numeric(active_df['value'], errors='coerce').fillna(0)
            total_assets = active_df['val_num'].sum()
            assets_active = active_df.to_dict(orient='records')

    # Goals calculation
    total_savings = 0.0
    total_target_goals = 0.0
    total_goals_count = 0
    goals_list = []
    if not df_goals.empty:
        total_goals_count = len(df_goals)
        df_goals_calc = df_goals.copy()
        df_goals_calc['curr'] = pd.to_numeric(df_goals_calc['current_amount'], errors='coerce').fillna(0)
        df_goals_calc['targ'] = pd.to_numeric(df_goals_calc['target_amount'], errors='coerce').fillna(0)
        running_goals = df_goals_calc[df_goals_calc['curr'] < df_goals_calc['targ']]
        total_savings = running_goals['curr'].sum()
        total_target_goals = running_goals['targ'].sum()
        goals_list = df_goals.to_dict(orient='records')

    budgets_list = []
    if not df_budgets.empty:
        for _, row in df_budgets.iterrows():
            b_dict = row.to_dict()
            cat_name = str(b_dict.get('category', ''))
            
            # Safely check both 'limit' and 'monthly_limit'
            val = row.get('limit')
            if pd.isna(val) or str(val).strip() == '' or str(val).lower() == 'nan':
                val = row.get('monthly_limit', 0.0)

            try:
                limit_val = float(val) if pd.notna(val) and str(val).strip() != '' and str(val).lower() != 'nan' else 0.0
            except (ValueError, TypeError):
                limit_val = 0.0

            spent_val = float(spent_map.get(cat_name, 0.0))
            is_exceeded = spent_val > limit_val if limit_val > 0 else False
            
            # Populate both keys so the template always finds the correct value
            b_dict['limit'] = limit_val
            b_dict['monthly_limit'] = limit_val
            b_dict['spent'] = spent_val
            b_dict['spent_amount'] = spent_val
            b_dict['exceeded'] = is_exceeded
            b_dict['status'] = 'Exceeded' if is_exceeded else 'Within Budget'
            
            budgets_list.append(b_dict)

    return render_template('index.html',
                           total_transactions=total_transactions,
                           total_income=total_income,
                           total_expense=total_expense,
                           net_balance=net_balance,
                           total_assets=total_assets,
                           total_savings=total_savings,
                           total_target_goals=total_target_goals,
                           total_goals_count=total_goals_count,
                           incomes=incomes,
                           expenses=expenses,
                           assets=assets_active,
                           all_assets=all_assets,
                           goals=goals_list,
                           budgets=budgets_list,
                           start_date=start_date,
                           end_date=end_date)

@main_bp.route('/reports', methods=['GET'])
def reports_page():
    today = date.today()
    default_start = today.replace(day=1).strftime('%Y-%m-%d')
    default_end = today.strftime('%Y-%m-%d')

    start_date = request.args.get('start_date', default_start)
    end_date = request.args.get('end_date', default_end)
    if not start_date:
        start_date = default_start
    if not end_date:
        end_date = default_end

    df_trans = load_csv_safely(os.path.join(DATA_DIR, 'transactions.csv'), ['id', 'date', 'type', 'title', 'amount', 'category'])
    df_assets = load_csv_safely(os.path.join(DATA_DIR, 'assets.csv'), ['id', 'date', 'name', 'value', 'type', 'status'])
    df_budgets = load_csv_safely(os.path.join(DATA_DIR, 'budgets.csv'), ['id', 'category', 'limit'])

    # Determine correct limit column name in budgets.csv
    limit_col = 'limit' if 'limit' in df_budgets.columns else 'monthly_limit'

    df_trans_filtered = df_trans.copy()
    if not df_trans_filtered.empty and 'date' in df_trans_filtered.columns:
        df_trans_filtered['date_dt'] = pd.to_datetime(df_trans_filtered['date'], errors='coerce')
        if start_date:
            df_trans_filtered = df_trans_filtered[df_trans_filtered['date_dt'] >= pd.to_datetime(start_date)]
        if end_date:
            df_trans_filtered = df_trans_filtered[df_trans_filtered['date_dt'] <= pd.to_datetime(end_date)]
        df_trans_filtered = df_trans_filtered.drop(columns=['date_dt'])

    if not df_trans_filtered.empty and 'amount' in df_trans_filtered.columns:
        df_trans_filtered['amount'] = pd.to_numeric(df_trans_filtered['amount'], errors='coerce').fillna(0)

    rep_total_income = df_trans_filtered[df_trans_filtered['type'].str.lower() == 'income']['amount'].sum() if not df_trans_filtered.empty else 0
    rep_total_expense = df_trans_filtered[df_trans_filtered['type'].str.lower() == 'expense']['amount'].sum() if not df_trans_filtered.empty else 0
    rep_net_savings = rep_total_income - rep_total_expense

    cat_expense_summary = {}
    if not df_trans_filtered.empty:
        df_exp = df_trans_filtered[df_trans_filtered['type'].str.lower() == 'expense']
        if not df_exp.empty:
            cat_expense_summary = df_exp.groupby('category')['amount'].sum().to_dict()

    cat_expenses_all = df_trans_filtered[df_trans_filtered['type'].str.lower() == 'expense'].groupby('category')['amount'].sum().to_dict() if not df_trans_filtered.empty else {}
    
    budgets_status = []
    if not df_budgets.empty:
        for _, row in df_budgets.iterrows():
            cat = row['category']
            val = row.get(limit_col, 0.0)
            limit = float(val) if pd.notna(val) and str(val).strip() != '' else 0.0
            spent = float(cat_expenses_all.get(cat, 0.0))
            budgets_status.append({
                'category': cat,
                'monthly_limit': limit,
                'spent': spent,
                'exceeded': spent > limit
            })

    logs_feed = []
    if not df_trans_filtered.empty:
        for _, row in df_trans_filtered.iterrows():
            logs_feed.append({
                'date': row['date'],
                'type': f"Transaction ({row['type'].capitalize()})",
                'description': f"{row['title']} - {row['amount']} ({row['category']})",
                'badge_class': 'income' if row['type'].lower() == 'income' else 'expense'
            })

    if not df_assets.empty:
        for _, row in df_assets.iterrows():
            a_date = row['date']
            if not start_date or not end_date or (start_date <= a_date <= end_date):
                status = row.get('status', 'active')
                logs_feed.append({
                    'date': a_date,
                    'type': f"Asset ({status.capitalize()})",
                    'description': f"{row['name']} valued at {row['value']} [{row['type']}]",
                    'badge_class': 'asset'
                })

    logs_feed = sorted(logs_feed, key=lambda x: x['date'], reverse=True)

    return render_template('reports.html',
                           start_date=start_date,
                           end_date=end_date,
                           rep_total_income=rep_total_income,
                           rep_total_expense=rep_total_expense,
                           rep_net_savings=rep_net_savings,
                           cat_expense_summary=cat_expense_summary,
                           budgets_status=budgets_status,
                           logs_feed=logs_feed)

@main_bp.route('/reports/export/financial', methods=['GET'])
def export_financial_csv():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    df_trans = load_csv_safely(os.path.join(DATA_DIR, 'transactions.csv'), ['id', 'date', 'type', 'title', 'amount', 'category'])
    if not df_trans.empty and 'date' in df_trans.columns:
        df_trans['date_dt'] = pd.to_datetime(df_trans['date'], errors='coerce')
        if start_date:
            df_trans = df_trans[df_trans['date_dt'] >= pd.to_datetime(start_date)]
        if end_date:
            df_trans = df_trans[df_trans['date_dt'] <= pd.to_datetime(end_date)]
        df_trans = df_trans.drop(columns=['date_dt'], errors='ignore')

    csv_data = df_trans.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=financial_report_{start_date}_to_{end_date}.csv"}
    )

@main_bp.route('/reports/export/logs', methods=['GET'])
def export_logs_csv():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    logs_path = os.path.join(DATA_DIR, 'activity_logs.csv')
    df_logs = load_csv_safely(logs_path, ['id', 'date', 'activity_type', 'description'])
    
    if not df_logs.empty and 'date' in df_logs.columns and (start_date or end_date):
        df_logs['date_dt'] = pd.to_datetime(df_logs['date'], errors='coerce')
        if start_date:
            df_logs = df_logs[df_logs['date_dt'] >= pd.to_datetime(start_date)]
        if end_date:
            df_logs = df_logs[df_logs['date_dt'] <= pd.to_datetime(end_date)]
        df_logs = df_logs.drop(columns=['date_dt'], errors='ignore')
        
    csv_data = df_logs.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=activity_audit_logs_{start_date}_to_{end_date}.csv"}
    )