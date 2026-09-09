import calendar
import os
import uuid
from datetime import date, datetime

import pandas as pd
from flask import Blueprint, redirect, render_template, request, url_for

from utils import DATA_DIR, load_csv_safely, log_activity

subscriptions_bp = Blueprint('subscriptions', __name__)


def _next_month(value):
    year = value.year + (value.month == 12)
    month = 1 if value.month == 12 else value.month + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def process_due_subscriptions():
    """Create one expense for every subscription renewal that is due."""
    subscriptions_path = os.path.join(DATA_DIR, 'subscriptions.csv')
    transactions_path = os.path.join(DATA_DIR, 'transactions.csv')
    df_subs = load_csv_safely(subscriptions_path, ['id', 'name', 'amount', 'category', 'billing_day', 'next_renewal', 'status'])
    df_transactions = load_csv_safely(transactions_path, ['id', 'date', 'type', 'title', 'amount', 'category'])
    if df_subs.empty:
        return 0

    today = date.today()
    created = 0
    for index, sub in df_subs.iterrows():
        if str(sub.get('status', '')).lower() != 'active':
            continue
        try:
            renewal = datetime.strptime(str(sub['next_renewal']), '%Y-%m-%d').date()
            amount = float(sub['amount'])
        except (ValueError, TypeError):
            continue
        while renewal <= today:
            title = f"Subscription: {sub['name']}"
            duplicate = ((df_transactions['title'].astype(str) == title) &
                         (df_transactions['date'].astype(str) == renewal.isoformat()) &
                         (df_transactions['type'].astype(str).str.lower() == 'expense'))
            if not duplicate.any():
                df_transactions = pd.concat([df_transactions, pd.DataFrame([{
                    'id': str(uuid.uuid4())[:8], 'date': renewal.isoformat(), 'type': 'Expense',
                    'title': title, 'amount': amount, 'category': sub['category'] or 'Subscriptions'
                }])], ignore_index=True)
                created += 1
            renewal = _next_month(renewal)
        df_subs.at[index, 'next_renewal'] = renewal.isoformat()
    if created:
        df_transactions.to_csv(transactions_path, index=False)
        log_activity('Subscription renewed', f'Added {created} scheduled subscription expense(s)')
    df_subs.to_csv(subscriptions_path, index=False)
    return created


@subscriptions_bp.route('/subscriptions', methods=['GET', 'POST'])
def subscriptions_page():
    subscriptions_path = os.path.join(DATA_DIR, 'subscriptions.csv')
    df_subs = load_csv_safely(subscriptions_path, ['id', 'name', 'amount', 'category', 'billing_day', 'next_renewal', 'status'])
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            amount = request.form.get('amount', '').strip()
            category = request.form.get('category', 'Subscriptions').strip() or 'Subscriptions'
            billing_day = request.form.get('billing_day', '').strip()
            if not name or not amount or not billing_day:
                return redirect(url_for('subscriptions.subscriptions_page', notification='Please complete every field.', notif_type='error'))
            try:
                amount = float(amount)
                billing_day = int(billing_day)
                if amount <= 0 or not 1 <= billing_day <= 31:
                    raise ValueError
            except ValueError:
                return redirect(url_for('subscriptions.subscriptions_page', notification='Use a positive amount and a billing day from 1 to 31.', notif_type='error'))
            today = date.today()
            renewal = date(today.year, today.month, min(billing_day, calendar.monthrange(today.year, today.month)[1]))
            if renewal < today:
                renewal = _next_month(renewal)
            df_subs = pd.concat([df_subs, pd.DataFrame([{
                'id': str(uuid.uuid4())[:8], 'name': name, 'amount': amount, 'category': category,
                'billing_day': billing_day, 'next_renewal': renewal.isoformat(), 'status': 'active'
            }])], ignore_index=True)
            df_subs.to_csv(subscriptions_path, index=False)
            log_activity('Subscription added', f"Added {name}, renewing monthly on day {billing_day}")
            return redirect(url_for('subscriptions.subscriptions_page', notification='Subscription saved.', notif_type='success'))
        sub_id = request.form.get('id')
        if action == 'toggle':
            current = df_subs.loc[df_subs['id'].astype(str) == str(sub_id), 'status']
            if not current.empty:
                df_subs.loc[df_subs['id'].astype(str) == str(sub_id), 'status'] = 'paused' if str(current.iloc[0]).lower() == 'active' else 'active'
                df_subs.to_csv(subscriptions_path, index=False)
            return redirect(url_for('subscriptions.subscriptions_page'))
        if action == 'delete':
            df_subs = df_subs[df_subs['id'].astype(str) != str(sub_id)]
            df_subs.to_csv(subscriptions_path, index=False)
            return redirect(url_for('subscriptions.subscriptions_page', notification='Subscription removed.', notif_type='success'))

    process_due_subscriptions()
    df_subs = load_csv_safely(subscriptions_path, ['id', 'name', 'amount', 'category', 'billing_day', 'next_renewal', 'status'])
    active = df_subs[df_subs['status'].str.lower() == 'active'].copy() if not df_subs.empty else df_subs
    monthly_total = pd.to_numeric(active['amount'], errors='coerce').fillna(0).sum() if not active.empty else 0
    return render_template('subscriptions.html', subscriptions=df_subs.sort_values('next_renewal').to_dict(orient='records') if not df_subs.empty else [], monthly_total=monthly_total, notification=request.args.get('notification', ''), notif_type=request.args.get('notif_type', 'success'))
