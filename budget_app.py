import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="My Mobile Budget", layout="centered")

# 2. Establish Secure Connection
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl=0)
except Exception as e:
    st.error(f"Waiting for secure handshake... Error: {e}")
    df = pd.DataFrame(columns=["Date", "Merchant", "Category", "Amount"])

# 3. Create the App Navigation (The Tabs)
tab_budget, tab_transactions = st.tabs(["📊 Budget", "💳 Transactions"])

# ==========================================
# 📊 VIEW 1: THE BUDGET TAB
# ==========================================
with tab_budget:
    st.header("February 2026") # We can make this dynamic later!
    
    # Core Metrics
    income = st.number_input("Planned Income ($)", min_value=0.0, value=5000.0)
    total_spent = df['Amount'].sum() if not df.empty else 0.0
    remaining = income - total_spent
    
    col1, col2 = st.columns(2)
    col1.metric("Remaining to Assign", f"${remaining:,.2f}")
    col2.metric("Total Spent", f"${total_spent:,.2f}")
    
    st.divider()
    st.info("🔧 Next Phase: We will build the 'Planned vs. Spent' categories right here!")

# ==========================================
# 💳 VIEW 2: THE TRANSACTIONS TAB
# ==========================================
with tab_transactions:
    st.header("Log Activity")
    
    # The Input Form
    with st.form("entry_form", clear_on_submit=True):
        t_date = st.date_input("Date")
        t_merch = st.text_input("Merchant")
        # Kept your custom categories ready to go
        t_cat = st.selectbox("Category", ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])
        t_amt = st.number_input("Amount ($)", min_value=0.0)
        
        if st.form_submit_button("Securely Sync Transaction", use_container_width=True):
            if t_merch and t_amt > 0:
                new_row = pd.DataFrame([[str(t_date), t_merch, t_cat, t_amt]], columns=df.columns)
                updated_df = pd.concat([df, new_row], ignore_index=True)
                
                conn.update(data=updated_df)
                st.success("✅ Transaction Permanently Saved!")
                st.rerun()
            else:
                st.warning("Please enter a merchant and an amount.")

    # The Database Readout
    st.subheader("Recent History")
    if not df.empty:
        # Changed from st.table to st.dataframe for a cleaner mobile look
        st.dataframe(df.iloc[::-1].head(10), use_container_width=True, hide_index=True)
