from datetime import date
import os
import uuid
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, Response
from utils import DATA_DIR, load_csv_safely, log_activity

assets_bp = Blueprint('assets', __name__)

@assets_bp.route('/assets', methods=['GET', 'POST'])
def assets_page():
    assets_path = os.path.join(DATA_DIR, 'assets.csv')
    cat_path = os.path.join(DATA_DIR, 'categories.csv')
    trans_path = os.path.join(DATA_DIR, 'transactions.csv')

    df_assets = load_csv_safely(assets_path, ['id', 'date', 'name', 'value', 'type', 'status'])
    if not df_assets.empty:
        if 'id' in df_assets.columns:
            df_assets['id'] = df_assets['id'].astype(str)
        if 'value' in df_assets.columns:
            df_assets['value'] = df_assets['value'].astype(str)
        if 'status' not in df_assets.columns:
            df_assets['status'] = 'active'
        else:
            df_assets['status'] = df_assets['status'].fillna('active')

    df_cat = load_csv_safely(cat_path, ['id', 'name', 'type'])

    edit_asset = None
    edit_id = request.args.get('edit_id')
    current_date_str = date.today().strftime('%Y-%m-%d')
    
    notification = request.args.get('notification', '')
    notif_type = request.args.get('notif_type', 'success')

    if request.method == 'POST':
        action = request.form.get('action')
        current_tab = request.form.get('tab', 'active')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        search_query = request.form.get('search', '')

        if action == 'add':
            date_val = request.form.get('date')
            name = request.form.get('name')
            value = request.form.get('value')
            a_type = request.form.get('type')
            
            if not date_val or not name or not value or not a_type:
                return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: All fields are required!", notif_type="error"))

            try:
                float(value)
            except ValueError:
                return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: Value must be a valid number!", notif_type="error"))

            new_id = str(uuid.uuid4())[:8]
            new_row = pd.DataFrame([{
                'id': new_id, 
                'date': str(date_val), 
                'name': str(name), 
                'value': str(value), 
                'type': str(a_type), 
                'status': 'active'
            }])
            df_assets.to_csv(assets_path, index=False)
            df_assets = pd.concat([df_assets, new_row], ignore_index=True)
            log_activity("Asset Added", f"Added asset '{name}' valued at {value} [{a_type}]")
            return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Asset added successfully!", notif_type="success"))

        elif action == 'update':
            a_id = request.form.get('id')
            date_val = request.form.get('date')
            name = request.form.get('name')
            value = request.form.get('value')
            a_type = request.form.get('type')
            
            if not a_id or not date_val or not name or not value or not a_type:
                return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Failed: All fields are required for update!", notif_type="error"))

            df_assets.loc[df_assets['id'] == str(a_id), ['date', 'name', 'value', 'type']] = [str(date_val), str(name), str(value), str(a_type)]
            df_assets.to_csv(assets_path, index=False)
            log_activity("Asset Updated", f"Updated asset details for '{name}' ({value})")
            return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Asset updated successfully!", notif_type="success"))

        elif action == 'sell':
            a_id = request.form.get('id')
            if a_id and not df_assets.empty:
                matched_asset = df_assets[df_assets['id'] == str(a_id)]
                if not matched_asset.empty:
                    asset_row = matched_asset.iloc[0]
                    asset_name = asset_row['name']
                    asset_value = asset_row['value']
                    asset_date = asset_row['date']
                    
                    df_trans = load_csv_safely(trans_path, ['id', 'date', 'type', 'title', 'amount', 'category'])
                    if not df_trans.empty and 'id' in df_trans.columns:
                        df_trans['id'] = df_trans['id'].astype(str)
                        
                    new_trans_id = str(uuid.uuid4())[:8]
                    new_trans_row = pd.DataFrame([{
                        'id': new_trans_id,
                        'date': str(asset_date),
                        'type': 'income',
                        'title': f"Sold: {asset_name}",
                        'amount': str(asset_value),
                        'category': 'Asset Sell'
                    }])
                    df_trans = pd.concat([df_trans, new_trans_row], ignore_index=True)
                    df_trans.to_csv(trans_path, index=False)
                    
                    if df_cat.empty or not ((df_cat['name'].str.lower() == 'asset sell') & (df_cat['type'].str.lower() == 'income')).any():
                        new_cat_id = str(uuid.uuid4())[:8]
                        new_cat_row = pd.DataFrame([{'id': new_cat_id, 'name': 'Asset Sell', 'type': 'income'}])
                        df_cat = pd.concat([df_cat, new_cat_row], ignore_index=True)
                        df_cat.to_csv(cat_path, index=False)

                    df_assets.loc[df_assets['id'] == str(a_id), 'status'] = 'sold'
                    df_assets.to_csv(assets_path, index=False)
                    log_activity("Asset Sold", f"Sold asset '{asset_name}' for {asset_value} and recorded as income")
            return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification=f"Asset '{asset_name}' sold successfully!", notif_type="success"))

        elif action == 'delete':
            a_id = request.form.get('id')
            df_assets = df_assets[df_assets['id'] != str(a_id)]
            df_assets.to_csv(assets_path, index=False)
            log_activity("Asset Deleted", f"Deleted asset record ID: {a_id}")
            return redirect(url_for('assets.assets_page', start_date=start_date, end_date=end_date, search=search_query, tab=current_tab, notification="Asset deleted successfully!", notif_type="success"))

    if edit_id and not df_assets.empty:
        matched = df_assets[df_assets['id'] == str(edit_id)]
        if not matched.empty:
            edit_asset = matched.iloc[0].to_dict()

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '').lower()
    tab = request.args.get('tab', 'active')

    df_filtered = df_assets.copy()
    if not df_filtered.empty:
        if 'status' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['status'].str.lower() == tab]
        else:
            df_filtered = df_filtered[tab == 'active']

        if 'date' in df_filtered.columns:
            df_filtered['date_dt'] = pd.to_datetime(df_filtered['date'], errors='coerce')
            if start_date:
                df_filtered = df_filtered[df_filtered['date_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_filtered = df_filtered[df_filtered['date_dt'] <= pd.to_datetime(end_date)]
            df_filtered = df_filtered.drop(columns=['date_dt'])
        
        if search_query:
            mask = (
                df_filtered['name'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['type'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_filtered['value'].astype(str).str.lower().str.contains(search_query, na=False)
            )
            df_filtered = df_filtered[mask]

    asset_categories = df_cat[df_cat['type'].str.lower() == 'asset']['name'].tolist() if not df_cat.empty else []
    assets_list = df_filtered.to_dict(orient='records') if not df_filtered.empty else []

    return render_template('assets.html', assets=assets_list, asset_categories=asset_categories, edit_asset=edit_asset, start_date=start_date, end_date=end_date, search_query=search_query, tab=tab, current_date=current_date_str, notification=notification, notif_type=notif_type)

@assets_bp.route('/assets/export')
def export_assets():
    assets_path = os.path.join(DATA_DIR, 'assets.csv')
    df_assets = load_csv_safely(assets_path, ['id', 'date', 'name', 'value', 'type', 'status'])

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '').lower()
    tab = request.args.get('tab', 'active')

    if not df_assets.empty:
        if 'status' in df_assets.columns:
            df_assets = df_assets[df_assets['status'].str.lower() == tab]
        
        if 'date' in df_assets.columns:
            df_assets['date_dt'] = pd.to_datetime(df_assets['date'], errors='coerce')
            if start_date:
                df_assets = df_assets[df_assets['date_dt'] >= pd.to_datetime(start_date)]
            if end_date:
                df_assets = df_assets[df_assets['date_dt'] <= pd.to_datetime(end_date)]
            df_assets = df_assets.drop(columns=['date_dt'])
        
        if search_query:
            mask = (
                df_assets['name'].astype(str).str.lower().str.contains(search_query, na=False) |
                df_assets['type'].astype(str).str.lower().str.contains(search_query, na=False)
            )
            df_assets = df_assets[mask]

    csv_data = df_assets.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=filtered_{tab}_assets.csv"}
    )