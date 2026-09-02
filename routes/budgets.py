import os
import uuid
import pandas as pd
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for,Response
from utils import DATA_DIR, load_csv_safely, log_activity

budgets_bp = Blueprint('budgets', __name__)

@budgets_bp.route('/budgets', methods=['GET', 'POST'])
def budgets_page():
    budgets_path = os.path.join(DATA_DIR, 'budgets.csv')
    trans_path = os.path.join(DATA_DIR, 'transactions.csv')
    cat_path = os.path.join(DATA_DIR, 'categories.csv')

    df_budgets = load_csv_safely(budgets_path, ['id', 'category', 'limit'])
    df_trans = load_csv_safely(trans_path, ['id', 'date', 'type', 'title', 'amount', 'category'])
    df_cat = load_csv_safely(cat_path, ['id', 'name', 'type'])

    # Explicitly cast columns to string to prevent int64 assignment TypeErrors
    if not df_budgets.empty:
        if 'id' in df_budgets.columns:
            df_budgets['id'] = df_budgets['id'].astype(str)
        if 'limit' in df_budgets.columns:
            df_budgets['limit'] = df_budgets['limit'].astype(str)
        if 'monthly_limit' in df_budgets.columns:
            df_budgets['monthly_limit'] = df_budgets['monthly_limit'].astype(str)

    # Extract expense categories list for the modal dropdown script
    exp_categories = []
    if not df_cat.empty and 'name' in df_cat.columns and 'type' in df_cat.columns:
        exp_df = df_cat[df_cat['type'].str.lower() == 'expense']
        exp_categories = exp_df['name'].dropna().astype(str).tolist()

    notification = request.args.get('notification', '')
    notif_type = request.args.get('notif_type', 'success')
    search_query = request.args.get('search', '').lower()

    limit_col = 'limit' if 'limit' in df_budgets.columns else 'monthly_limit'

    # Calculate current month's spending to reset budgets automatically every month
    current_year_month = date.today().strftime('%Y-%m')
    spent_map = {}
    if not df_trans.empty and 'date' in df_trans.columns and 'amount' in df_trans.columns:
        df_trans_calc = df_trans.copy()
        df_trans_calc['date_dt'] = pd.to_datetime(df_trans_calc['date'], errors='coerce')
        df_trans_calc['amount_num'] = pd.to_numeric(df_trans_calc['amount'], errors='coerce').fillna(0)
        
        current_month_trans = df_trans_calc[
            (df_trans_calc['date_dt'].dt.strftime('%Y-%m') == current_year_month) & 
            (df_trans_calc['type'].str.lower() == 'expense')
        ]
        if not current_month_trans.empty:
            spent_map = current_month_trans.groupby('category')['amount_num'].sum().to_dict()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            category = request.form.get('category')
            limit_val = request.form.get('limit')

            if not category or not limit_val:
                return redirect(url_for('budgets.budgets_page', notification="Failed: Category and limit are required!", notif_type="error"))

            try:
                float(limit_val)
            except ValueError:
                return redirect(url_for('budgets.budgets_page', notification="Failed: Limit must be a valid number!", notif_type="error"))

            if not df_budgets.empty and (df_budgets['category'].str.lower() == category.lower()).any():
                return redirect(url_for('budgets.budgets_page', notification=f"Failed: Budget for category '{category}' already exists!", notif_type="error"))

            new_id = str(uuid.uuid4())[:8]
            new_row = pd.DataFrame([{
                'id': str(new_id),
                'category': str(category),
                limit_col: str(limit_val)
            }])
            df_budgets = pd.concat([df_budgets, new_row], ignore_index=True)
            df_budgets.to_csv(budgets_path, index=False)
            log_activity("Budget Created", f"Created monthly budget limit of ${limit_val} for category '{category}'")
            return redirect(url_for('budgets.budgets_page', notification="Budget added successfully!", notif_type="success"))

        elif action == 'update':
            b_id = request.form.get('id')
            category = request.form.get('category')
            limit_val = request.form.get('limit')

            if not b_id or not category or not limit_val:
                return redirect(url_for('budgets.budgets_page', notification="Failed: All fields are required for update!", notif_type="error"))

            try:
                float(limit_val)
            except ValueError:
                return redirect(url_for('budgets.budgets_page', notification="Failed: Limit must be a valid number!", notif_type="error"))

            if not df_budgets.empty and 'id' in df_budgets.columns:
                df_budgets.loc[df_budgets['id'] == str(b_id), ['category', limit_col]] = [str(category), str(limit_val)]
                df_budgets.to_csv(budgets_path, index=False)
                log_activity("Budget Updated", f"Updated budget limit for category '{category}' to ${limit_val}")
                return redirect(url_for('budgets.budgets_page', notification="Budget updated successfully!", notif_type="success"))
            else:
                return redirect(url_for('budgets.budgets_page', notification="Failed: Budget record not found!", notif_type="error"))

        elif action == 'delete':
            b_id = request.form.get('id')
            if b_id and not df_budgets.empty:
                df_budgets = df_budgets[df_budgets['id'] != str(b_id)]
                df_budgets.to_csv(budgets_path, index=False)
                log_activity("Budget Deleted", f"Deleted budget ID: {b_id}")
                return redirect(url_for('budgets.budgets_page', notification="Budget deleted successfully!", notif_type="success"))

    budgets_list = []
    if not df_budgets.empty:
        for _, row in df_budgets.iterrows():
            b_dict = row.to_dict()
            cat_name = str(b_dict.get('category', ''))
            lim = float(b_dict.get(limit_col, 0) or 0)
            spent = float(spent_map.get(cat_name, 0.0))
            
            b_dict['limit'] = lim
            b_dict['spent'] = spent
            b_dict['status'] = 'Exceeded' if spent > lim else 'Within Budget'
            budgets_list.append(b_dict)

    if search_query:
        budgets_list = [
            b for b in budgets_list 
            if search_query in str(b.get('category', '')).lower() or search_query in str(b.get('limit', '')).lower()
        ]

    return render_template('budgets.html',
                           budgets=budgets_list,
                           exp_categories=exp_categories,
                           search_query=search_query,
                           notification=notification,
                           notif_type=notif_type)

@budgets_bp.route('/budgets/export')
def export_budgets():
    budgets_path = os.path.join(DATA_DIR, 'budgets.csv')
    df_budgets = load_csv_safely(budgets_path, ['id', 'category', 'limit'])
    csv_data = df_budgets.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=budgets.csv"}
    )