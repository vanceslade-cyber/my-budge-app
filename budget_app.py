import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="My Mobile Budget", layout="centered")
st.title("💰 My Permanent Budget")

# 2. Establish Secure Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Read Existing Data
# ttl=0 ensures we always see the most recent data from the sheet
df = conn.read(ttl=0)

# 4. Calculations (The EveryDollar Logic)
income = st.sidebar.number_input("Monthly Income ($)", min_value=0.0, value=5000.0)
total_spent = df['Amount'].sum() if not df.empty else 0.0
remaining = income - total_spent

col1, col2 = st.columns(2)
col1.metric("Remaining to Assign", f"${remaining:,.2f}")
col2.metric("Total Spent", f"${total_spent:,.2f}")

# 5. Input Form
st.divider()
with st.expander("➕ Log New Transaction", expanded=True):
    with st.form("entry_form", clear_on_submit=True):
        t_date = st.date_input("Date")
        t_merch = st.text_input("Merchant")
        t_cat = st.selectbox("Category", ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])
        t_amt = st.number_input("Amount ($)", min_value=0.0)
        
        if st.form_submit_button("Save to Google Sheets", use_container_width=True):
            if t_merch and t_amt > 0:
                # Create a new row of data
                new_row = pd.DataFrame([{
                    "Date": str(t_date),
                    "Merchant": t_merch,
                    "Category": t_cat,
                    "Amount": t_amt
                }])
                
                # Add the new row to our existing data
                updated_df = pd.concat([df, new_row], ignore_index=True)
                
                # Write the whole thing back to the Google Sheet
                # Note: This will use the URL in your 'Secrets'
                conn.update(data=updated_df)
                
                st.success("Transaction Securely Synced!")
                st.rerun()
            else:
                st.warning("Please enter a merchant and an amount.")
# 6. Display Recent Transactions
st.subheader("Recent Activity")
if not df.empty:
    st.table(df.iloc[::-1].head(10)) st.form_submit_button("Save to Google Sheets", use_container_width=True):
            if t_merch and t_amt > 0:
                new_row = pd.DataFrame([{
                    "Date": str(t_date),
                    "Merchant": t_merch,
                    "Category": t_cat,
                    "Amount": t_amt
                }])
                
                # Combine existing data with the new row
                updated_df = pd.concat([df, new_row], ignore_index=True)
                
                # Use 'worksheet="Sheet1"' to be explicit (Check your tab name at the bottom of Google Sheets!)
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success("Transaction Securely Synced!")
                st.rerun()
            else:
                st.warning("Please enter a merchant and an amount.")
