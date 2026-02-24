import streamlit as st
import pandas as pd
import os

# 1. Page Config (This makes it look like an app on your phone)
st.set_page_config(page_title="My Budget", layout="centered")

st.title("💰 My Mobile Budget")

# 2. Data Loading
csv_file = "my_budget_data.csv"
if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
else:
    df = pd.DataFrame(columns=["Date", "Merchant", "Category", "Amount"])

# 3. Income Section (Using a 'metric' card looks better on mobile)
income = st.sidebar.number_input("Monthly Income ($)", min_value=0.0, value=5000.0)
total_spent = df['Amount'].sum() if not df.empty else 0.0
remaining = income - total_spent

col1, col2 = st.columns(2)
col1.metric("Remaining", f"${remaining:,.2f}")
col2.metric("Total Spent", f"${total_spent:,.2f}")

# 4. Simple Input Form (Big buttons for mobile)
st.divider()
with st.expander("➕ Log New Transaction", expanded=True):
    with st.form("entry_form", clear_on_submit=True):
        t_date = st.date_input("Date")
        t_merch = st.text_input("Merchant")
        t_cat = st.selectbox("Category", ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])
        t_amt = st.number_input("Amount ($)", min_value=0.0)
        
        if st.form_submit_button("Save Transaction", use_container_width=True):
            new_data = pd.DataFrame([[t_date, t_merch, t_cat, t_amt]], columns=df.columns)
            df = pd.concat([df, new_data], ignore_index=True)
            df.to_csv(csv_file, index=False)
            st.success("Saved!")
            st.rerun()

# 5. Recent Activity
st.subheader("Recent Spending")
if not df.empty:
    # Sort by date so newest is at the top
    st.table(df.sort_index(ascending=False).head(10))