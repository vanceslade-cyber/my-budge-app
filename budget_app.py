import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# 1. Page Config
st.set_page_config(page_title="My Mobile Budget", layout="centered")

# --- TIME TRAVEL STATE MANAGEMENT ---
# Set the default view to the current month/year
if 'view_date' not in st.session_state:
    st.session_state.view_date = datetime.date.today().replace(day=1)

def change_month(months_to_add):
    """Calculates the new month and year when you click the arrows"""
    new_month = st.session_state.view_date.month - 1 + months_to_add
    new_year = st.session_state.view_date.year + new_month // 12
    new_month = new_month % 12 + 1
    st.session_state.view_date = datetime.date(new_year, new_month, 1)

# 2. Establish Secure Connection
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Read the MASTER sheet
    df = conn.read(ttl=0)
except Exception as e:
    st.error(f"Waiting for secure handshake... Error: {e}")
    df = pd.DataFrame(columns=["Date", "Merchant", "Category", "Amount"])

# 3. Filter Data by Selected Month
filtered_df = df.copy()
if not filtered_df.empty:
    # Convert text dates into actual 'Time Objects'
    filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
    
    # Create the 'Filter Lens'
    mask = (filtered_df['Date'].dt.month == st.session_state.view_date.month) & \
           (filtered_df['Date'].dt.year == st.session_state.view_date.year)
    filtered_df = filtered_df[mask]

# --- APP HEADER (MONTH TOGGLE) ---
st.title("💰 Permanent Budget")

col_left, col_mid, col_right = st.columns([1, 3, 1])
with col_left:
    st.button("◀", on_click=change_month, args=(-1,), use_container_width=True)
with col_mid:
    # Displays e.g., "February 2026"
    current_month_str = st.session_state.view_date.strftime("%B %Y")
    st.markdown(f"<h3 style='text-align: center; margin-top: 0px;'>{current_month_str}</h3>", unsafe_allow_html=True)
with col_right:
    st.button("▶", on_click=change_month, args=(1,), use_container_width=True)

st.divider()

# 4. Create the App Navigation
tab_budget, tab_transactions = st.tabs(["📊 Budget", "💳 Transactions"])

# ==========================================
# 📊 VIEW 1: THE BUDGET TAB
# ==========================================
with tab_budget:
    # Notice we are now doing math on 'filtered_df', not the master 'df'
    income = st.number_input("Planned Income ($)", min_value=0.0, value=5000.0)
    total_spent = filtered_df['Amount'].sum() if not filtered_df.empty else 0.0
    remaining = income - total_spent
    
    col1, col2 = st.columns(2)
    col1.metric("Remaining to Assign", f"${remaining:,.2f}")
    col2.metric("Total Spent", f"${total_spent:,.2f}")
    
    st.info("🔧 Next Phase: We will build the 'Planned vs. Spent' categories right here!")

# ==========================================
# 💳 VIEW 2: THE TRANSACTIONS TAB
# ==========================================
with tab_transactions:
    with st.form("entry_form", clear_on_submit=True):
        # Default the date picker to the month we are currently looking at!
        t_date = st.date_input("Date", value=st.session_state.view_date)
        t_merch = st.text_input("Merchant")
        t_cat = st.selectbox("Category", ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])
        t_amt = st.number_input("Amount ($)", min_value=0.0)
        
        if st.form_submit_button("Securely Sync Transaction", use_container_width=True):
            if t_merch and t_amt > 0:
                new_row = pd.DataFrame([[str(t_date), t_merch, t_cat, t_amt]], columns=df.columns)
                
                # We append to the MASTER 'df', not the filtered one, to save it properly!
                updated_df = pd.concat([df, new_row], ignore_index=True)
                
                conn.update(data=updated_df)
                st.success("✅ Transaction Permanently Saved!")
                st.rerun()
            else:
                st.warning("Please enter a merchant and an amount.")

    st.subheader(f"History for {current_month_str}")
    if not filtered_df.empty:
        # Format the date nicely before displaying
        display_df = filtered_df.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df.iloc[::-1].head(10), use_container_width=True, hide_index=True)
    else:
        st.write("No transactions logged for this month yet.")
