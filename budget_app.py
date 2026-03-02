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

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(worksheet="Sheet1", ttl=0)
    if 'Type' not in df.columns:
        df['Type'] = 'Expense'
    df['Type'] = df['Type'].fillna('Expense')
except Exception as e:
    st.error(f"Transaction handshake failed. Error: {e}")
    df = pd.DataFrame(columns=["Date", "Type", "Merchant", "Category", "Amount"])

try:
    plan_df = conn.read(worksheet="Plan", ttl=0)
except Exception as e:
    st.error(f"Plan handshake failed. Error: {e}")
    plan_df = pd.DataFrame(columns=["Month", "Type", "Category", "Planned_Amount"])

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

# --- MODALS (Pop-ups) ---
@st.dialog("➕ Add Transaction")
def transaction_modal():
    with st.form("entry_form", clear_on_submit=True):
        tx_type = st.radio("Type", ["- Expense", "+ Income"], horizontal=True, label_visibility="collapsed")
        st.divider()
        
        local_now = datetime.datetime.now(ZoneInfo("America/Edmonton")).date()
        t_date = st.date_input("Date", value=local_now)
        t_amt = st.number_input("Amount ($)", min_value=0.00, value=0.00, step=0.01)
        t_merch = st.text_input("Merchant", placeholder="Enter Name")
        
        planned_items = month_plan_df['Category'].dropna().unique().tolist() if not month_plan_df.empty else []
        t_cat = st.selectbox("Budget Item(s)", ["Select >"] + planned_items + ["Other"])

        st.divider()
        if st.form_submit_button("Securely Sync Transaction", use_container_width=True):
            if t_merch and t_amt >= 0 and t_cat != "Select >":
                clean_type = tx_type.split(" ")[1] 
                new_row = pd.DataFrame([[str(t_date), clean_type, t_merch, t_cat, t_amt]], columns=["Date", "Type", "Merchant", "Category", "Amount"])
                try:
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(worksheet="Sheet1", data=updated_df)
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
                new_plan = pd.DataFrame([[current_month_key, "Income", i_name, i_amt]], columns=["Month", "Type", "Category", "Planned_Amount"])
                try:
                    updated_plan = pd.concat([plan_df, new_plan], ignore_index=True)
                    conn.update(worksheet="Plan", data=updated_plan)
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
                new_plan = pd.DataFrame([[current_month_key, section_name, i_name, i_amt]], columns=["Month", "Type", "Category", "Planned_Amount"])
                try:
                    updated_plan = pd.concat([plan_df, new_plan], ignore_index=True)
                    conn.update(worksheet="Plan", data=updated_plan)
                    st.success(f"✅ Added to {section_name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Write unauthorized. Error: {e}")
            else:
                st.warning("Please enter a name and amount.")

# --- APP HEADER ---
st.title("💰 Budget Manager")
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
    
    total_planned_income = income_df['Planned_Amount'].astype(float).sum() if not income_df.empty else 0.0
    expense_df = filtered_df[filtered_df['Type'] != 'Income'] if not filtered_df.empty else pd.DataFrame()
    total_spent = expense_df['Amount'].astype(float).sum() if not expense_df.empty else 0.0
    remaining = total_planned_income - total_spent
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Planned Income", f"${total_planned_income:,.2f}")
    col2.metric("Left to Assign", f"${remaining:,.2f}")
    col3.metric("Total Spent", f"${total_spent:,.2f}")
    
    st.write("") 
    
    # --- 1. THE INCOME SECTION ---
    st.markdown(
        f"""
        <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
            <h5 style='color: gray; margin-bottom: 0px;'>Income</h5>
            <span style='color: gray; margin-bottom: 0px;'>{budget_view}</span>
        </div>
        <hr style='margin-top: 5px; margin-bottom: 10px;'>
        """, unsafe_allow_html=True
    )
    
    if not income_df.empty:
        for index, row in income_df.iterrows():
            planned_amt = float(row['Planned_Amount'])
            
            # BROKEN DOWN PANDAS LOGIC TO PREVENT WORD-WRAP ERRORS
            if not filtered_df.empty:
                is_cat = filtered_df['Category'] == row['Category']
                is_inc = filtered_df['Type'] == 'Income'
                cat_spent = filtered_df[is_cat & is_inc]['Amount'].astype(float).sum()
            else:
                cat_spent = 0.0
            
            if budget_view ==
