import streamlit as st
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

st.set_page_config(page_title="My Budget", layout="centered")

# --- STATE MANAGEMENT ---
if 'view_date' not in st.session_state:
    local_now = datetime.datetime.now(ZoneInfo("America/Edmonton")).date()
    st.session_state.view_date = local_now.replace(day=1)

def change_month(months_to_add):
    new_month = st.session_state.view_date.month - 1 + months_to_add
    # Handle year rollover
    new_year = st.session_state.view_date.year + (new_month // 12)
    new_month = (new_month % 12) + 1
    st.session_state.view_date = datetime.date(new_year, new_month, 1)

# --- HELPER: BULLETPROOF NUMBER PARSER ---
def safe_float(val):
    try:
        # Strip out dollar signs, commas, and hidden spaces
        return float(str(val).replace('$', '').replace(',', '').strip())
    except:
        return 0.0

# --- DATABASE CONNECTION & SCHEMA ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(worksheet="Sheet1", ttl=0)
    df.columns = df.columns.str.strip()
    if 'Type' not in df.columns: df['Type'] = 'Expense'
    if 'Description' not in df.columns: df['Description'] = ""
    
    df['Type'] = df['Type'].astype(str).str.strip().fillna('Expense')
    df['Category'] = df['Category'].astype(str).str.strip()
    df['Description'] = df['Description'].fillna("")
    df['Amount'] = df['Amount'].apply(safe_float)
except Exception as e:
    st.error(f"Transaction handshake failed. Error: {e}")
    df = pd.DataFrame(columns=["Date", "Type", "Merchant", "Category", "Amount", "Description"])

try:
    plan_df = conn.read(worksheet="Plan", ttl=0)
    plan_df.columns = plan_df.columns.str.strip() 
    
    # Ensure columns exist to prevent crashes
    for col in ["Month", "Type", "Category", "Planned_Amount", "Due_Date", "Is_Fund", "Current_Balance", "Target_Balance"]:
        if col not in plan_df.columns:
            plan_df[col] = ""

    plan_df['Type'] = plan_df['Type'].astype(str).str.strip()
    plan_df['Category'] = plan_df['Category'].astype(str).str.strip()
    plan_df['Due_Date'] = plan_df['Due_Date'].fillna("")
    
    # THE STRING LOCK: Converts everything to literal YES/NO text for GSheets
    plan_df['Is_Fund'] = plan_df['Is_Fund'].astype(str).str.strip().str.upper()
    plan_df['Is_Fund'] = plan_df['Is_Fund'].apply(lambda x: "YES" if x in ['TRUE', '1', 'T', 'Y', 'YES'] else "NO")
    
    plan_df['Planned_Amount'] = plan_df['Planned_Amount'].apply(safe_float)
    plan_df['Current_Balance'] = plan_df['Current_Balance'].apply(safe_float)
    plan_df['Target_Balance'] = plan_df['Target_Balance'].apply(safe_float)
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
    clean_cat_name = str(category_name).strip()
    clean_cat_type = str(category_type).strip()
    
    mask = (plan_df['Month'] == current_m_key) & (plan_df['Category'] == clean_cat_name)
    if not plan_df[mask].empty:
        row_idx = plan_df[mask].index[0]
        current_plan_row = plan_df.loc[row_idx]
    else:
        st.error("Item not found.")
        return

    st.subheader(clean_cat_name)

    # 1. TRANSACTIONS SECTION
    st.markdown("**Activity This Month**")
    cat_tx_mask = (pd.to_datetime(df['Date'], errors='coerce').dt.month == st.session_state.view_date.month) & \
                  (pd.to_datetime(df['Date'], errors='coerce').dt.year == st.session_state.view_date.year) & \
                  (df['Category'] == clean_cat_name)
    
    cat_tx_df = df[cat_tx_mask].reset_index(drop=True)
    
    if not cat_tx_df.empty:
        st.caption("💡 Select a row on the left to delete, or double-click to edit.")
        edit_cols = ['Date', 'Merchant', 'Description', 'Amount']
        edited_cat_tx = st.data_editor(cat_tx_df[edit_cols], num_rows="dynamic", use_container_width=True, key=f"edit_tx_{clean_cat_name}_{current_m_key}")
        
        if st.button("🗑️ Save Transaction Changes", use_container_width=True, key=f"btn_save_tx_{clean_cat_name}_{current_m_key}"):
            edited_cat_tx['Category'] = clean_cat_name
            default_type = cat_tx_df['Type'].iloc[0] if not cat_tx_df.empty else ('Expense' if clean_cat_type != 'Income' else 'Income')
            edited_cat_tx['Type'] = default_type
            edited_cat_tx = edited_cat_tx[["Date", "Type", "Merchant", "Category", "Amount", "Description"]]
            
            df_remaining = df[~cat_tx_mask]
            updated_master_tx = pd.concat([df_remaining, edited_cat_tx], ignore_index=True)
            try:
                conn.update(worksheet="Sheet1", data=updated_master_tx)
                st.cache_data.clear() 
                st.success("✅ Transactions Updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.caption(f"No transactions logged for {clean_cat_name} this month.")

    make_fund = False
    c_bal = 0.0
    t_bal = 0.0

    # 2. FUND SECTION
    if clean_cat_type == "Savings":
        st.divider()
        st.markdown("**🐖 Fund**")
        
        is_fund_status = str(current_plan_row.get('Is_Fund', 'NO')).strip().upper() == "YES"
        make_fund = st.toggle("Make Fund", value=is_fund_status, key=f"fund_toggle_{clean_cat_name}_{current_m_key}")
        
        if make_fund:
            st.info("Balances carry over month to month.")
            c_bal = safe_float(current_plan_row.get('Current_Balance', 0.0))
            t_bal = safe_float(current_plan_row.get('Target_Balance', 0.0))
            
            st.markdown("<p style='color: gray; font-size: small; margin-bottom: 0px;'>Current Balance ($)</p>", unsafe_allow_html=True)
            c_bal = st.number_input("Current Balance ($)", value=c_bal, min_value=0.0, step=10.0, label_visibility="collapsed", key=f"cbal_{clean_cat_name}_{current_m_key}")
            
            st.markdown("<p style='color: gray; font-size: small; margin-bottom: 0px;'>Target Amount ($)</p>", unsafe_allow_html=True)
            t_bal = st.number_input("Target Amount ($)", value=t_bal, min_value=0.0, step=10.0, label_visibility="collapsed", key=f"tbal_{clean_cat_name}_{current_m_key}")
            
            if t_bal > 0:
                progress = min(c_bal / t_bal, 1.0)
                st.progress(progress)
                st.caption(f"🎯 **{progress*100:.1f}%** to Goal")

    # 3. SCHEDULE SECTION
    st.divider()
    existing_due = current_plan_row.get('Due_Date', "")
    parsed_due = None
    if pd.notna(existing_due) and str(existing_due).strip():
        try: parsed_due = datetime.datetime.strptime(str(existing_due)[:10], "%Y-%m-%d").date()
        except: pass
    
    st.markdown("**📅 Schedule**")
    st.markdown("<p style='color: gray; font-size: small; margin-bottom: 0px;'>Due Date</p>", unsafe_allow_html=True)
    d_date = st.date_input("Due Date", value=parsed_due, label_visibility="collapsed", key=f"due_date_{clean_cat_name}_{current_m_key}")

    st.divider()
    if st.button("💾 Save Item Settings", type="primary", use_container_width=True, key=f"save_settings_{clean_cat_name}_{current_m_key}"):
        plan_df.loc[row_idx, 'Due_Date'] = str(d_date) if d_date else ""
        if clean_cat_type == "Savings":
            plan_df.loc[row_idx, 'Is_Fund'] = "YES" if make_fund else "NO"
            plan_df.loc[row_idx, 'Current_Balance'] = float(c_bal)
            plan_df.loc[row_idx, 'Target_Balance'] = float(t_bal)

        try:
            conn.update(worksheet="Plan", data=plan_df)
            st.cache_data.clear() 
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
        t
