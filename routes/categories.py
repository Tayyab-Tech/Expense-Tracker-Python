import os
import uuid
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for
from utils import DATA_DIR, load_csv_safely, log_activity

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/categories', methods=['GET', 'POST'])
def categories_page():
    cat_path = os.path.join(DATA_DIR, 'categories.csv')
    trans_path = os.path.join(DATA_DIR, 'transactions.csv')
    assets_path = os.path.join(DATA_DIR, 'assets.csv')

    df_cat = load_csv_safely(cat_path, ['id', 'name', 'type'])
    if not df_cat.empty and 'id' in df_cat.columns:
        df_cat['id'] = df_cat['id'].astype(str)

    notification = request.args.get('notification', '')
    notif_type = request.args.get('notif_type', 'success')
    search_query = request.args.get('search', '').lower()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            name = request.form.get('name')
            c_type = request.form.get('type')
            
            if not name or not c_type:
                return redirect(url_for('categories.categories_page', notification="Failed: Category name and type are required!", notif_type="error"))

            if not df_cat.empty and ((df_cat['name'].str.lower() == name.lower()) & (df_cat['type'].str.lower() == c_type.lower())).any():
                return redirect(url_for('categories.categories_page', notification=f"Failed: Category '{name}' already exists for {c_type}!", notif_type="error"))

            new_id = str(uuid.uuid4())[:8]
            new_row = pd.DataFrame([{'id': new_id, 'name': str(name), 'type': str(c_type)}])
            df_cat = pd.concat([df_cat, new_row], ignore_index=True)
            df_cat.to_csv(cat_path, index=False)
            log_activity("Category Added", f"Added category '{name}' [{c_type}]")
            return redirect(url_for('categories.categories_page', notification="Category added successfully!", notif_type="success"))

        elif action == 'delete':
            c_id = request.form.get('id')
            if not c_id or df_cat.empty:
                return redirect(url_for('categories.categories_page', notification="Failed: Invalid category ID!", notif_type="error"))

            matched = df_cat[df_cat['id'] == str(c_id)]
            if matched.empty:
                return redirect(url_for('categories.categories_page', notification="Failed: Category not found!", notif_type="error"))

            cat_row = matched.iloc[0]
            cat_name = cat_row['name']
            cat_type = str(cat_row['type'])

            # Check if category is used in transactions (Income / Expense)
            df_trans = load_csv_safely(trans_path, ['id', 'date', 'type', 'title', 'amount', 'category'])
            is_used_in_trans = False
            if not df_trans.empty and 'category' in df_trans.columns:
                is_used_in_trans = (df_trans['category'].str.lower() == cat_name.lower()).any()

            # Check if category is used in assets
            df_assets = load_csv_safely(assets_path, ['id', 'date', 'name', 'value', 'type', 'status'])
            is_used_in_assets = False
            if not df_assets.empty and 'type' in df_assets.columns:
                is_used_in_assets = (df_assets['type'].str.lower() == cat_name.lower()).any()

            if is_used_in_trans or is_used_in_assets:
                return redirect(url_for('categories.categories_page', notification=f"Warning: Cannot delete category '{cat_name}' because it is currently in use by recorded transactions or assets!", notif_type="error"))

            df_cat = df_cat[df_cat['id'] != str(c_id)]
            df_cat.to_csv(cat_path, index=False)
            log_activity("Category Deleted", f"Deleted category '{cat_name}' [{cat_type}]")
            return redirect(url_for('categories.categories_page', notification="Category deleted successfully!", notif_type="success"))

    df_filtered = df_cat.copy()
    if search_query and not df_filtered.empty:
        mask = (
            df_filtered['name'].astype(str).str.lower().str.contains(search_query, na=False) |
            df_filtered['type'].astype(str).str.lower().str.contains(search_query, na=False)
        )
        df_filtered = df_filtered[mask]

    categories_list = df_filtered.to_dict(orient='records') if not df_filtered.empty else []

    return render_template('categories.html', 
                           categories=categories_list, 
                           search_query=search_query,
                           notification=notification,
                           notif_type=notif_type)