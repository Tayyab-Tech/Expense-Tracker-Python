import os
import uuid
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, Response
from utils import DATA_DIR, load_csv_safely, log_activity

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('/goals', methods=['GET', 'POST'])
def goals_page():
    goals_path = os.path.join(DATA_DIR, 'goals.csv')
    df_goals = load_csv_safely(goals_path, ['id', 'title', 'target_amount', 'current_amount', 'deadline'])
    
    if not df_goals.empty:
        if 'id' in df_goals.columns:
            df_goals['id'] = df_goals['id'].astype(str)
        if 'target_amount' in df_goals.columns:
            df_goals['target_amount'] = df_goals['target_amount'].astype(str)
        if 'current_amount' in df_goals.columns:
            df_goals['current_amount'] = df_goals['current_amount'].astype(str)

    edit_goal = None
    edit_id = request.args.get('edit_id')
    current_date_str = pd.Timestamp.today().strftime('%Y-%m-%d')
    
    notification = request.args.get('notification', '')
    notif_type = request.args.get('notif_type', 'success')

    if request.method == 'POST':
        action = request.form.get('action')
        current_tab = request.form.get('tab', 'all')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        search_query = request.form.get('search', '')

        if action == 'add':
            title = request.form.get('title')
            target_amount = request.form.get('target_amount')
            current_amount = request.form.get('current_amount', '0')
            deadline = request.form.get('deadline')
            
            if not title or not target_amount or not deadline:
                return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: Title, target amount, and deadline are required!", notif_type="error"))

            try:
                float(target_amount)
                float(current_amount)
            except ValueError:
                return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: Amounts must be valid numbers!", notif_type="error"))

            new_id = str(uuid.uuid4())[:8]
            new_row = pd.DataFrame([{
                'id': new_id, 
                'title': str(title), 
                'target_amount': str(target_amount), 
                'current_amount': str(current_amount), 
                'deadline': str(deadline)
            }])
            df_goals = pd.concat([df_goals, new_row], ignore_index=True)
            df_goals.to_csv(goals_path, index=False)
            log_activity("Goal Created", f"Created financial goal '{title}' with target {target_amount}")
            return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Financial goal added successfully!", notif_type="success"))

        elif action == 'update':
            g_id = request.form.get('id')
            title = request.form.get('title')
            target_amount = request.form.get('target_amount')
            current_amount = request.form.get('current_amount', '0')
            deadline = request.form.get('deadline')
            
            if not g_id or not title or not target_amount or not deadline:
                return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: All fields are required for update!", notif_type="error"))

            df_goals.loc[df_goals['id'] == str(g_id), ['title', 'target_amount', 'current_amount', 'deadline']] = [str(title), str(target_amount), str(current_amount), str(deadline)]
            df_goals.to_csv(goals_path, index=False)
            log_activity("Goal Updated", f"Updated financial goal '{title}'")
            return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Financial goal updated successfully!", notif_type="success"))

        elif action == 'add_saving':
            g_id = request.form.get('id')
            try:
                add_amount = float(request.form.get('add_amount', 0))
            except ValueError:
                add_amount = 0

            if g_id and add_amount > 0:
                current = float(df_goals.loc[df_goals['id'] == str(g_id), 'current_amount'].values[0] or 0)
                new_current = current + add_amount
                df_goals.loc[df_goals['id'] == str(g_id), 'current_amount'] = str(new_current)
                df_goals.to_csv(goals_path, index=False)
                log_activity("Goal Savings Added", f"Added {add_amount} to goal savings")
                return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification=f"Successfully added {add_amount} to savings!", notif_type="success"))
            else:
                return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: Enter a valid saving amount greater than 0!", notif_type="error"))

        elif action == 'delete':
            g_id = request.form.get('id')
            df_goals = df_goals[df_goals['id'] != str(g_id)]
            df_goals.to_csv(goals_path, index=False)
            log_activity("Goal Deleted", f"Deleted goal record ID: {g_id}")
            return redirect(url_for('goals.goals_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Financial goal deleted successfully!", notif_type="success"))

    if edit_id and not df_goals.empty:
        matched = df_goals[df_goals['id'] == str(edit_id)]
        if not matched.empty:
            edit_goal = matched.iloc[0].to_dict()

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '').lower()
    tab = request.args.get('tab', 'all')

    df_filtered = df_goals.copy()
    if not df_filtered.empty:
        if 'deadline' in df_filtered.columns:
            df_filtered['deadline_dt'] = pd.to_datetime(df_filtered['deadline'], errors='coerce')
            if start_date:
                df_filtered = df_filtered[df_filtered['deadline_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_filtered = df_filtered[df_filtered['deadline_dt'] <= pd.to_datetime(end_date)]
            df_filtered = df_filtered.drop(columns=['deadline_dt'])
        
        if search_query:
            mask = (
                df_filtered['title'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['target_amount'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['current_amount'].astype(str).str.lower().str.contains(search_query, na=False)
            )
            df_filtered = df_filtered[mask]

    goals_list = []
    if not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            g_dict = row.to_dict()
            curr = float(g_dict.get('current_amount', 0) or 0)
            targ = float(g_dict.get('target_amount', 0) or 0)
            completed = curr >= targ
            g_dict['completed'] = completed
            
            if tab == 'completed' and not completed:
                continue
            if tab == 'running' and completed:
                continue
                
            goals_list.append(g_dict)

    return render_template('goals.html', goals=goals_list, edit_goal=edit_goal, start_date=start_date, end_date=end_date, search_query=search_query, tab=tab, current_date=current_date_str, notification=notification, notif_type=notif_type)

@goals_bp.route('/goals/export')
def export_goals():
    goals_path = os.path.join(DATA_DIR, 'goals.csv')
    df_goals = load_csv_safely(goals_path, ['id', 'title', 'target_amount', 'current_amount', 'deadline'])

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '').lower()
    tab = request.args.get('tab', 'all')

    if not df_goals.empty:
        if 'deadline' in df_goals.columns:
            df_goals['deadline_dt'] = pd.to_datetime(df_goals['deadline'], errors='coerce')
            if start_date:
                df_goals = df_goals[df_goals['deadline_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_goals = df_goals[df_goals['deadline_dt'] <= pd.to_datetime(end_date)]
            df_goals = df_goals.drop(columns=['deadline_dt'])
        
        if search_query:
            mask = (
                df_goals['title'].astype(str).str.lower().str.contains(search_query, na=False)
            )
            df_goals = df_goals[mask]

        filtered_rows = []
        for _, row in df_goals.iterrows():
            curr = float(row.get('current_amount', 0) or 0)
            targ = float(row.get('target_amount', 0) or 0)
            completed = curr >= targ
            
            if tab == 'completed' and not completed:
                continue
            if tab == 'running' and completed:
                continue
            filtered_rows.append(row)
            
        df_goals = pd.DataFrame(filtered_rows) if filtered_rows else pd.DataFrame(columns=df_goals.columns)

    csv_data = df_goals.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=filtered_goals.csv"}
    )