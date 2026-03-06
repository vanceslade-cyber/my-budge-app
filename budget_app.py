import streamlit as st
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

st.set_page_config(page_title="EveryDollar Clone", layout="centered")

# --- STATE MANAGEMENT ---
if 'view_date' not in st.session_state:
    local_now = datetime.datetime.now(ZoneInfo("America/Edmonton")).date()
    st.session_state.view_date = local_now.replace(day=1)

def change_month(months_to_add):
    new_month = st.session_state.view_date.month - 1 + months_to_add
    new_year = st.session_state.view_date.year + new_month // 12
    new_month = new_month % 12 + 1
    st.session_state.view_date = datetime.date(new_year, new_month, 1)

# --- DATABASE CONNECTION & SCHEMA ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(worksheet="Sheet1", ttl=0)
    if 'Type' not in df.columns: df['Type'] = 'Expense'
    if 'Description' not in df.columns: df['Description'] = ""
    
    df['Type'] = df['Type'].fillna('Expense')
    df['Description'] = df['Description'].fillna("")
except Exception as e:
    st.error(f"Transaction handshake failed. Error: {e}")
    df = pd.DataFrame(columns=["Date", "Type", "Merchant", "Category", "Amount", "Description"])

try:
    plan_df = conn.read(worksheet="Plan", ttl=0)
    if 'Due_Date' not in plan_df.columns: plan_df['Due_Date'] = ""
    if 'Is_Fund' not in plan_df.columns: plan_df['Is_Fund'] = False
    if 'Current_Balance' not in plan_df.columns: plan_df['Current_Balance'] = 0.0
    if 'Target_Balance' not in plan_df.columns: plan_df['Target_Balance'] = 0.0

    plan_df['Due_Date'] = plan_df['Due_Date'].fillna("")
    
    # Bulletproof boolean casting
    plan_df['Is_Fund'] = plan_df['Is_Fund'].astype(str).str.strip().str.lower().isin(['true', '1', 't', 'y', 'yes'])
    
    plan_df['Current_Balance'] = pd.to_numeric(plan_df['Current_Balance'], errors='coerce').fillna(0.0)
    plan_df['Target_Balance'] = pd.to_numeric(plan_df['Target_Balance'], errors='coerce').fillna(0.0)
except Exception as e:
    st.error(f"Plan handshake failed. Error: {e}")
    plan_df = pd.DataFrame(columns=["Month", "Type", "Category", "Planned_Amount", "Due_Date", "Is_Fund", "Current_Balance", "Target_Balance"])

# --- DATA FILTERING ---
current_month_str = st.session_state.view_date.strftime("%B %Y")
current_month_key = st.session_state.view_date.strftime("%Y-%m")

filtered_df = df.copy()
if not filtered_df.empty:
    filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
    mask = (filtered_df['Date'].dt.month == st.session_state.view_date.month) & \
           (filtered_df['Date'].dt.year == st.session_state.view_date.year)
    filtered_df = filtered_df[mask]

month_plan_df = plan_df[plan_df['Month'] == current_month_key] if not plan_df.empty else pd.DataFrame()
income_df = month_plan_df[month_plan_df['Type'] == 'Income'] if not month_plan_df.empty else pd.DataFrame()

# --- THE ITEM DETAILS MODAL ---
@st.dialog("📋 Item Details")
def item_details_modal(category_name, category_type, current_m_key):
    mask = (plan_df['Month'] == current_m_key) & (plan_df['Category'] == category_name)
    if not plan_df[mask].empty:
        row_idx = plan_df[mask].index[0]
        current_plan_row = plan_df.loc[row_idx]
    else:
        st.error("Item not found.")
        return

    st.subheader(category_name)

    st.markdown("**Activity This Month**")
    cat_tx_mask = (pd.to_datetime(df['Date'], errors='coerce').dt.month == st.session_state.view_date.month) & \
                  (pd.to_datetime(df['Date'], errors='coerce').dt.year == st.session_state.view_date.year) & \
                  (df['Category'] == category_name)
    
    cat_tx_df = df[cat_tx_mask].reset_index(drop=True)
    
    if not cat_tx_df.empty:
        st.caption("💡 Select a row on the left to delete, or double-click to edit.")
        edit_cols = ['Date', 'Merchant', 'Description', 'Amount']
        edited_cat_tx = st.data_editor(cat_tx_df[edit_cols], num_rows="dynamic", use_container_width=True, key=f"edit_tx_{category_name}_{current_m_key}")
        
        if st.button("🗑️ Save Transaction Changes", use_container_width=True, key=f"btn_save_tx_{category_name}_{current_m_key}"):
            edited_cat_tx['Category'] = category_name
            default_type = cat_tx_df['Type'].iloc[0] if not cat_tx_df.empty else ('Expense' if category_type != 'Income' else 'Income')
            edited_cat_tx['Type'] = default_type
            edited_cat_tx = edited_cat_tx[["Date", "Type", "Merchant", "Category", "Amount", "Description"]]
            
            df_remaining = df[~cat_tx_mask]
            updated_master_tx = pd.concat([df_remaining, edited_cat_tx], ignore_index=True)
            try:
                conn.update(worksheet="Sheet1", data=updated_master_tx)
                st.cache_data.clear() # 🚨 FORCING CACHE WIPE
                st.success("✅ Transactions Updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.caption(f"No transactions logged for {category_name} this month.")

    st.divider()

    existing_due = current_plan_row.get('Due_Date', "")
    parsed_due = None
    if pd.notna(existing_due) and str(existing_due).strip():
        try: parsed_due = datetime.datetime.strptime(str(existing_due)[:10], "%Y-%m-%d").date()
        except: pass
    
    st.markdown("**📅 Schedule**")
    st.markdown("<p style='color: gray; font-size: small; margin-bottom: 0px;'>Due Date</p>", unsafe_allow_html=True)
    d_date = st.date_input("Due Date", value=parsed_due, label_visibility="collapsed", key=f"due_date_{category_name}_{current_m_key}")

    make_fund = False
    c_bal = 0.0
    t_bal = 0.0
    
    if category_type == "Savings":
        st.divider()
        st.markdown("**🐖 Fund**")
        
        is_fund = bool(current_plan_row.get('Is_Fund', False))
        
        make_fund = st.toggle("Make Fund", value=is_fund, key=f"fund_toggle_{category_name}_{current_m_key}")
        
        if make_fund:
            st.info("Balances carry over month to month.")
            c_bal = float(current_plan_row.get('Current_Balance', 0.0))
            t_bal = float(current_plan_row.get('Target_Balance', 0.0))
            
            st.markdown("<p style='color: gray; font-size: small; margin-bottom: 0px;'>Current Balance ($)</p>", unsafe_allow_html=True)
            c_bal = st.number_input("Current Balance ($)", value=c_bal, min_value=0.0, step=10.0, label_visibility="collapsed", key=f"cbal_{category_name}_{current_m_key}")
            
            st.markdown("<p style='color: gray; font-size: small; margin-bottom: 0px;'>Target Amount ($)</p>", unsafe_allow_html=True)
            t_bal = st.number_input("Target Amount ($)", value=t_bal, min_value=0.0, step=10.0, label_visibility="collapsed", key=f"tbal_{category_name}_{current_m_key}")
            
            if t_bal > 0:
                progress = min(c_bal / t_bal, 1.0)
                st.progress(progress)
                st.caption(f"🎯 **{progress*100:.1f}%** to Goal")

    st.divider()
    if st.button("💾 Save Item Settings", type="primary", use_container_width=True, key=f"save_settings_{category_name}_{current_m_key}"):
        plan_df.at[row_idx, 'Due_Date'] = str(d_date) if d_date else ""
        if category_type == "Savings":
            plan_df.at[row_idx, 'Is_Fund'] = make_fund
            plan_df.at[row_idx, 'Current_Balance'] = float(c_bal)
            plan_df.at[row_idx, 'Target_Balance'] = float(t_bal)

        try:
            conn.update(worksheet="Plan", data=plan_df)
            st.cache_data.clear() # 🚨 FORCING CACHE WIPE
            st.success("✅ Settings Saved!")
            st.rerun()
        except Exception as e:
            st.error(f"Error saving: {e}")

# --- ADD ITEM MODALS ---
@st.dialog("➕ Add Transaction")
def transaction_modal():
    with st.form("entry_form", clear_on_submit=True):
        tx_type = st.radio("Type", ["- Expense", "+ Income"], horizontal=True, label_visibility="collapsed")
        st.divider()
        
        local_now = datetime.datetime.now(ZoneInfo("America/Edmonton")).date()
        t_date = st.date_input("Date", value=local_now)
        t_amt = st.number_input("Amount ($)", min_value=0.00, value=0.00, step=0.01)
        
        t_merch = st.text_input("Merchant", placeholder="Enter Name")
        t_desc = st.text_input("Description (Optional)", placeholder="e.g., Prescriptions, Groceries")
        
        planned_items = month_plan_df['Category'].dropna().unique().tolist() if not month_plan_df.empty else []
        t_cat = st.selectbox("Budget Item(s)", ["Select >"] + planned_items + ["Other"])

        st.divider()
        if st.form_submit_button("Securely Sync Transaction", use_container_width=True):
            if t_merch and t_amt >= 0 and t_cat != "Select >":
                clean_type = tx_type.split(" ")[1] 
                new_row = {"Date": str(t_date), "Type": clean_type, "Merchant": t_merch, "Category": t_cat, "Amount": t_amt, "Description": t_desc}
                new_tx = pd.DataFrame([new_row])
                try:
                    updated_df = pd.concat([df, new_tx], ignore_index=True)
                    conn.update(worksheet="Sheet1", data=updated_df)
                    st.cache_data.clear() # 🚨 FORCING CACHE WIPE
                    st.success("✅ Transaction Saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Write unauthorized. Error: {e}")
            else:
                st.warning("Please complete Date, Amount, Merchant, and Budget Item.")

@st.dialog("💵 Add Income")
def add_income_modal():
    with st.form("income_form", clear_on_submit=True):
        i_name = st.text_input("Income Name", placeholder="e.g., Tots Bucks")
        i_amt = st.number_input("Planned Amount ($)", min_value=0.00, value=0.00, step=10.00)
        
        if st.form_submit_button("Save Income", use_container_width=True):
            if i_name and i_amt >= 0:
                new_row = {"Month": current_month_key, "Type": "Income", "Category": i_name, "Planned_Amount": i_amt, "Due_Date": "", "Is_Fund": False, "Current_Balance": 0.0, "Target_Balance": 0.0}
                new_plan = pd.DataFrame([new_row])
                try:
                    updated_plan = pd.concat([plan_df, new_plan], ignore_index=True)
                    conn.update(worksheet="Plan", data=updated_plan)
                    st.cache_data.clear() # 🚨 FORCING CACHE WIPE
                    st.success("✅ Income Added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Write unauthorized. Error: {e}")
            else:
                st.warning("Please enter a name and amount.")

@st.dialog("➕ Add Planned Item")
def add_planned_item_modal(section_name):
    with st.form(f"form_{section_name}", clear_on_submit=True):
        st.markdown(f"Add new item to **{section_name}**")
        i_name = st.text_input("Item Name", placeholder="e.g., Groceries, Rent, Fuel")
        i_amt = st.number_input("Planned Amount ($)", min_value=0.00, value=0.00, step=10.00)
        
        if st.form_submit_button("Save Item", use_container_width=True):
            if i_name and i_amt >= 0:
                new_row = {"Month": current_month_key, "Type": section_name, "Category": i_name, "Planned_Amount": i_amt, "Due_Date": "", "Is_Fund": False, "Current_Balance": 0.0, "Target_Balance": 0.0}
                new_plan = pd.DataFrame([new_row])
                try:
                    updated_plan = pd.concat([plan_df, new_plan], ignore_index=True)
                    conn.update(worksheet="Plan", data=updated_plan)
                    st.cache_data.clear() # 🚨 FORCING CACHE WIPE
                    st.success(f"✅ Added to {section_name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Write unauthorized. Error: {e}")
            else:
                st.warning("Please enter a name and amount.")

# --- HELPER FUNCTION: Renders Dynamic Rows ---
def render_budget_row(row, group_name, budget_view_state, filtered_tx_df, current_m_key):
    planned_amt = float(row['Planned_Amount'])
    
    if not filtered_tx_df.empty:
        is_cat = filtered_tx_df['Category'] == row['Category']
        is_type = filtered_tx_df['Type'] == ('Income' if group_name == 'Income' else 'Expense')
        cat_spent = filtered_tx_df[is_cat & is_type]['Amount'].astype(float).sum()
    else:
        cat_spent = 0.0
    
    is_savings_fund = (group_name == "Savings") and row['Is_Fund']
    
    if is_savings_fund:
        starting_bal = float(row['Current_Balance'])
        spent_amt_to_display = cat_spent
        available_balance_to_display = starting_bal + planned_amt - cat_spent
    else:
        spent_amt_to_display = cat_spent
        available_balance_to_display = planned_amt - cat_spent

    if group_name == "Reimbursable":
        display_amt = cat_spent
    else:
        if budget_view_state == "Planned": display_amt = planned_amt
        elif budget_view_state == "Spent": display_amt = spent_amt_to_display
        else: display_amt = available_balance_to_display

    col_label, col_amt = st.columns([3, 1], vertical_alignment="center")
    with col_label:
        due_d_str = row['Due_Date']
        if pd.notna(due_d_str) and due_d_str.strip():
            col_modal_btn, col_modal_name = st.columns([1, 19], vertical_alignment="center")
            with col_modal_btn:
                if st.button("📝", type="tertiary", key=f"btn_details_m_{row['Category']}_{current_m_key}"):
                    item_details_modal(row['Category'], group_name, current_m_key)
            with col_modal_name:
                try:
                    due_obj = datetime.datetime.strptime(str(due_d_str)[:10], "%Y-%m-%d")
                    formatted_due = due_obj.strftime("%b %d")
                    st.markdown(f"<p style='color: gray; margin-bottom: 0px;'>{row['Category']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='color: gray; font-size: small; margin-top: -10px; margin-bottom: 0px;'>Due {formatted_due}</p>", unsafe_allow_html=True)
                except:
                    st.markdown(f"<p style='color: gray; margin-bottom: 0px;'>{row['Category']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='color: gray; font-size: small; margin-top: -10px; margin-bottom: 0px;'>Due {due_d_str}</p>", unsafe_allow_html=True)
        else:
            col_modal_btn, col_modal_name = st.columns([1, 19], vertical_alignment="center")
            with col_modal_btn:
                if st.button("📝", type="tertiary", key=f"btn_details_nm_{row['Category']}_{current_m_key}"):
                    item_details_modal(row['Category'], group_name, current_m_key)
            with col_modal_name:
                st.markdown(f"<p style='color: gray; margin-bottom: 0px;'>{row['Category']}</p>", unsafe_allow_html=True)

    with col_amt:
        st.markdown(f"<div style='text-align: right;'>${display_amt:,.2f}</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin-top: 0px; margin-bottom: 5px; border-top: 1px solid #e6e6e6;'>", unsafe_allow_html=True)


# --- APP HEADER ---
st.title("💰 My Budget")
col_left, col_mid, col_right, col_plus = st.columns([1, 3, 1, 1])
with col_left:
    st.button("◀", on_click=change_month, args=(-1,), use_container_width=True)
with col_mid:
    st.markdown(f"<h3 style='text-align: center; margin-top: 0px;'>{current_month_str}</h3>", unsafe_allow_html=True)
with col_right:
    st.button("▶", on_click=change_month, args=(1,), use_container_width=True)
with col_plus:
    if st.button("➕", use_container_width=True):
        transaction_modal()

st.divider()

# --- NAVIGATION TABS ---
tab_budget, tab_transactions, tab_manage = st.tabs(["📊 Budget", "💳 Transactions", "⚙️ Manage"])

# ==========================================
# 📊 VIEW 1: THE BUDGET TAB
# ==========================================
with tab_budget:
    budget_view = st.radio("Budget View", ["Planned", "Spent", "Remaining"], horizontal=True, label_visibility="collapsed")
    
    reimbursable_cats = month_plan_df[month_plan_df['Type'] == 'Reimbursable']['Category'].tolist() if not month_plan_df.empty else []
    total_planned_income = income_df['Planned_Amount'].astype(float).sum() if not income_df.empty else 0.0
    
    if not month_plan_df.empty:
        expense_plan_df = month_plan_df[(month_plan_df['Type'] != 'Income') & (month_plan_df['Type'] != 'Reimbursable')]
        total_planned_expenses = expense_plan_df['Planned_Amount'].astype(float).sum()
    else:
        total_planned_expenses = 0.0
        
    if not filtered_df.empty:
        expense_df = filtered_df[(filtered_df['Type'] != 'Income') & (~filtered_df['Category'].isin(reimbursable_cats))]
    else:
        expense_df = pd.DataFrame()
        
    total_spent = expense_df['Amount'].astype(float).sum() if not expense_df.empty else 0.0
    remaining_to_spend = total_planned_income - total_spent
    left_to_budget = total_planned_income - total_planned_expenses
    
    # --- 1. THE ZERO-BASED BANNER ---
    if left_to_budget > 0:
        st.info(f"You have **${left_to_budget:,.2f}** left to budget.")
    elif left_to_budget < 0:
        st.error(f"You are **${abs(left_to_budget):,.2f}** over budget.")
    else:
        st.success("✅ It's a zero-based budget!")
        
    st.write("")
    if total_planned_income > 0:
        spend_ratio = min(total_spent / total_planned_income, 1.0)
        st.markdown(f"<p style='text-align: center; color: gray; margin-bottom: 5px; font-size: small;'>Budget Utilization ({spend_ratio*100:.1f}%)</p>", unsafe_allow_html=True)
        st.progress(spend_ratio)
    st.write("")
        
    # --- 2. THE DYNAMIC HEADER METRIC ---
    if budget_view == "Planned":
        st.metric("Planned Income", f"${total_planned_income:,.2f}")
    elif budget_view == "Spent":
        st.metric("Spent So Far", f"${total_spent:,.2f}")
    else:
        st.metric("Remaining to Spend", f"${remaining_to_spend:,.2f}")
        
    st.write("") 
    
    # --- 3. THE INCOME SECTION ---
    inc_header_start = "<div style='display: flex; justify-content: space-between; align-items: flex-end;'>"
    inc_header_title = f"<h5 style='color: gray; margin-bottom: 0px;'>Income</h5>"
    inc_header_view = f"<span style='color: gray; margin-bottom: 0px;'>{budget_view}</span>"
    inc_header_end = "</div>"
    inc_header_divider = "<hr style='margin-top: 5px; margin-bottom: 10px;'>"
    
    st.markdown(inc_header_start + inc_header_title + inc_header_view + inc_header_end + inc_header_divider, unsafe_allow_html=True)
    
    if not income_df.empty:
        for index, row in income_df.iterrows():
            render_budget_row(row, "Income", budget_view, filtered_df, current_month_key)
    
    if st.button("Add Income", type="tertiary"):
        add_income_modal()

    st.write("") 
    st.write("") 

    # --- 4. THE DYNAMIC EXPENSE SECTIONS ---
    expense_groups = ["Giving", "Savings", "Housing", "Transportation", "Food", "Subscriptions", "Lifestyle", "Health", "Insurance", "Debt", "Reimbursable"]
    
    for group in expense_groups:
        group_df = month_plan_df[month_plan_df['Type'] == group] if not month_plan_df.empty else pd.DataFrame()
        
        exp_header_start = "<div style='display: flex; justify-content: space-between; align-items: flex-end;'>"
        exp_header_title = f"<h5 style='color: gray; margin-bottom: 0px;'>{group}</h5>"
        
        if group == "Reimbursable":
            exp_header_view = f"<span style='color: gray; margin-bottom: 0px;'>Total Spent</span>"
        else:
            exp_header_view = f"<span style='color: gray; margin-bottom: 0px;'>{budget_view}</span>"
            
        exp_header_end = "</div>"
        exp_header_divider = "<hr style='margin-top: 5px; margin-bottom: 10px;'>"
        
        st.markdown(exp_header_start + exp_header_title + exp_header_view + exp_header_end + exp_header_divider, unsafe_allow_html=True)
        
        if not group_df.empty:
            for index, row in group_df.iterrows():
                render_budget_row(row, group, budget_view, filtered_df, current_month_key)
        
        if st.button(f"Add {group}", type="tertiary", key=f"btn_add_{group}"):
            add_planned_item_modal(group)
            
        st.write("")

# ==========================================
# 💳 VIEW 2: THE TRANSACTIONS TAB
# ==========================================
with tab_transactions:
    st.subheader(f"History for {current_month_str}")
    
    if not filtered_df.empty:
        display_df = filtered_df.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        
        def style_rows(row):
            if 'Type' in row and row['Type'] == 'Income': return ['color: #1a8b4c'] * len(row) 
            else: return [''] * len(row)

        styled_df = display_df.iloc[::-1].head(10).style.apply(style_rows, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.write("No transactions logged for this month yet.")

# ==========================================
# ⚙️ VIEW 3: THE MANAGE TAB
# ==========================================
with tab_manage:
    st.info("💡 **How to use:** Double-click any cell to edit it. To delete an item, click the checkbox on the far left of its row, then click the trash can icon at the top right of the table.")
    
    st.subheader("💾 Offline Backup")
    st.caption("Download your master databases as CSV files for safekeeping.")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(label="📥 Download Transactions", data=df.to_csv(index=False), file_name="budget_transactions_backup.csv", mime="text/csv", use_container_width=True)
    with col_dl2:
        st.download_button(label="📥 Download Budget Plan", data=plan_df.to_csv(index=False), file_name="budget_plan_backup.csv", mime="text/csv", use_container_width=True)

    st.divider()

    st.subheader(f"Edit {current_month_str} Plan")
    plan_mask = plan_df['Month'] == current_month_key
    current_plan_view = plan_df[plan_mask].reset_index(drop=True)
    
    edited_plan = st.data_editor(current_plan_view, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Save Plan Changes", type="primary", use_container_width=True):
        plan_remaining = plan_df[~plan_mask]
        updated_master_plan = pd.concat([plan_remaining, edited_plan], ignore_index=True)
        try:
            conn.update(worksheet="Plan", data=updated_master_plan)
            st.cache_data.clear() # 🚨 FORCING CACHE WIPE
            st.success("✅ Plan Updated Permanently!")
            st.rerun()
        except Exception as e:
            st.error(f"Error saving: {e}")

    st.divider()

    st.subheader(f"Edit {current_month_str} Transactions")
    temp_dates = pd.to_datetime(df['Date'], errors='coerce')
    tx_mask = (temp_dates.dt.month == st.session_state.view_date.month) & (temp_dates.dt.year == st.session_state.view_date.year)
    current_tx_view = df[tx_mask].reset_index(drop=True)
    
    edited_tx = st.data_editor(current_tx_view, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Save Transaction Changes", type="primary", use_container_width=True):
        tx_remaining = df[~tx_mask]
        updated_master_tx = pd.concat([tx_remaining, edited_tx], ignore_index=True)
        try:
            conn.update(worksheet="Sheet1", data=updated_master_tx)
            st.cache_data.clear() # 🚨 FORCING CACHE WIPE
            st.success("✅ Transactions Updated Permanently!")
            st.rerun()
        except Exception as e:
            st.error(f"Error saving: {e}")
