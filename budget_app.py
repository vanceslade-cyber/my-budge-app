import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="My Mobile Budget", layout="centered")
st.title("💰 Permanent Mobile Budget")

# 1. Establish Secure Connection
# This automatically looks for the 'service_account' info in your Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Read Existing Data
try:
    df = conn.read(ttl=0)
except Exception as e:
    st.error(f"Waiting for secure handshake... Error: {e}")
    df = pd.DataFrame(columns=["Date", "Merchant", "Category", "Amount"])

# 3. Metrics (The EveryDollar Logic)
income = st.sidebar.number_input("Monthly Income ($)", min_value=0.0, value=5000.0)
total_spent = df['Amount'].sum() if not df.empty else 0.0
remaining = income - total_spent

col1, col2 = st.columns(2)
col1.metric("Remaining to Assign", f"${remaining:,.2f}")
col2.metric("Total Spent", f"${total_spent:,.2f}")

# 4. Transaction Form
with st.form("entry_form", clear_on_submit=True):
    t_date = st.date_input("Date")
    t_merch = st.text_input("Merchant")
    t_cat = st.selectbox("Category", ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])
    t_amt = st.number_input("Amount ($)", min_value=0.0)
    
    if st.form_submit_button("Securely Sync Transaction", use_container_width=True):
        if t_merch and t_amt > 0:
            new_row = pd.DataFrame([[str(t_date), t_merch, t_cat, t_amt]], columns=df.columns)
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
            # The "Update" call now uses your Service Account Key!
            conn.update(data=updated_df)
            st.success("✅ Transaction Permanently Saved!")
            st.rerun()

# 5. Display Table
st.subheader("Recent Activity")
if not df.empty:
    st.table(df.iloc[::-1].head(10))
