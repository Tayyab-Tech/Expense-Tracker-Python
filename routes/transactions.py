from datetime import date
import os
import uuid
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, Response
from utils import DATA_DIR, load_csv_safely, log_activity

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions', methods=['GET', 'POST'])
def transactions_page():
    trans_path = os.path.join(DATA_DIR, 'transactions.csv')
    cat_path = os.path.join(DATA_DIR, 'categories.csv')

    df_trans = load_csv_safely(trans_path, ['id', 'date', 'type', 'title', 'amount', 'category'])
    if not df_trans.empty and 'id' in df_trans.columns:
        df_trans['id'] = df_trans['id'].astype(str)

    df_cat = load_csv_safely(cat_path, ['id', 'name', 'type'])

    edit_transaction = None
    edit_id = request.args.get('edit_id')
    current_date_str = date.today().strftime('%Y-%m-%d')
    
    notification = request.args.get('notification', '')
    notif_type = request.args.get('notif_type', 'success')

    if request.method == 'POST':
        action = request.form.get('action')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        search_query = request.form.get('search', '')

        if action == 'add':
            date_val = request.form.get('date')
            t_type = request.form.get('type')
            title = request.form.get('title')
            amount = request.form.get('amount')
            category = request.form.get('category')
            if not date_val or not t_type or not title or not amount or not category:
                return redirect(url_for('transactions.transactions_page', start_date=start_date, end_date=end_date, search=search_query, notification="Failed: All fields are required!", notif_type="error"))

            try:
                float(amount)
            except ValueError:
                return redirect(url_for('transactions.transactions_page', start_date=start_date, end_date=end_date, search=search_query, notification="Failed: Amount must be a valid number!", notif_type="error"))

            new_id = str(uuid.uuid4())[:8]
            new_row = pd.DataFrame([{'id': new_id, 'date': str(date_val), 'type': str(t_type), 'title': str(title), 'amount': str(amount), 'category': str(category)}])
            df_trans = pd.concat([df_trans, new_row], ignore_index=True)
            df_trans.to_csv(trans_path, index=False)
            log_activity("Transaction Added", f"Added {t_type}: '{title}' for {amount} ({category})")
            return redirect(url_for('transactions.transactions_page', start_date=start_date, end_date=end_date, search=search_query, notification="Transaction added successfully!", notif_type="success"))

        elif action == 'update':
            t_id = request.form.get('id')
            date_val = request.form.get('date')
            t_type = request.form.get('type')
            title = request.form.get('title')
            amount = request.form.get('amount')
            category = request.form.get('category')
            
            if not t_id or not date_val or not t_type or not title or not amount or not category:
                return redirect(url_for('transactions.transactions_page', start_date=start_date, end_date=end_date, search=search_query, notification="Failed: All fields are required for update!", notif_type="error"))
            df_trans.loc[df_trans['id'] == str(t_id), ['date', 'type', 'title', 'amount', 'category']] = [str(date_val), str(t_type), str(title), str(amount), str(category)]
            df_trans.to_csv(trans_path, index=False)
            log_activity("Transaction Updated", f"Updated transaction '{title}' ({amount})")
            return redirect(url_for('transactions.transactions_page', start_date=start_date, end_date=end_date, search=search_query, notification="Transaction updated successfully!", notif_type="success"))

        elif action == 'delete':
            t_id = request.form.get('id')
            df_trans = df_trans[df_trans['id'] != str(t_id)]
            df_trans.to_csv(trans_path, index=False)
            log_activity("Transaction Deleted", f"Deleted transaction ID: {t_id}")
            return redirect(url_for('transactions.transactions_page', start_date=start_date, end_date=end_date, search=search_query, notification="Transaction deleted successfully!", notif_type="success"))
    if edit_id and not df_trans.empty:
        matched = df_trans[df_trans['id'] == str(edit_id)]
        if not matched.empty:
            edit_transaction = matched.iloc[0].to_dict()

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '').lower()

    df_filtered = df_trans.copy()
    if not df_filtered.empty:
        if 'date' in df_filtered.columns:
            df_filtered['date_dt'] = pd.to_datetime(df_filtered['date'], errors='coerce')
            if start_date:
                df_filtered = df_filtered[df_filtered['date_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_filtered = df_filtered[df_filtered['date_dt'] <= pd.to_datetime(end_date)]
            df_filtered = df_filtered.drop(columns=['date_dt'])
        
        if search_query:
            mask = (
                df_filtered['title'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['category'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['type'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['amount'].astype(str).str.lower().str.contains(search_query, na=False)
            )
            df_filtered = df_filtered[mask]

    incomes = df_filtered[df_filtered['type'].str.lower() == 'income'].to_dict(orient='records') if not df_filtered.empty else []
    expenses = df_filtered[df_filtered['type'].str.lower() == 'expense'].to_dict(orient='records') if not df_filtered.empty else []
    
    inc_categories = df_cat[df_cat['type'].str.lower() == 'income']['name'].tolist() if not df_cat.empty else []
    exp_categories = df_cat[df_cat['type'].str.lower() == 'expense']['name'].tolist() if not df_cat.empty else []

    return render_template('transactions.html', 
                           incomes=incomes, 
                           expenses=expenses, 
                           inc_categories=inc_categories, 
                           exp_categories=exp_categories,
                           edit_transaction=edit_transaction,
                           start_date=start_date,
                           end_date=end_date,
                           search_query=search_query,
                           current_date=current_date_str,
                           notification=notification,
                           notif_type=notif_type)

@transactions_bp.route('/transactions/export')
def export_transactions():
    trans_path = os.path.join(DATA_DIR, 'transactions.csv')
    df_trans = load_csv_safely(trans_path, ['id', 'date', 'type', 'title', 'amount', 'category'])

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '').lower()

    if not df_trans.empty:
        if 'date' in df_trans.columns:
            df_trans['date_dt'] = pd.to_datetime(df_trans['date'], errors='coerce')
            if start_date:
                df_trans = df_trans[df_trans['date_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_trans = df_trans[df_trans['date_dt'] <= pd.to_datetime(end_date)]
            df_trans = df_trans.drop(columns=['date_dt'])
        
        if search_query:
            mask = (
                df_trans['title'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_trans['category'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_trans['type'].astype(str).str.lower().str.contains(search_query, na=False)
            )
            df_trans = df_trans[mask]

    csv_data = df_trans.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=filtered_transactions.csv"}
    )