import streamlit as st
import pandas as pd
import os

# 1. Page Config
st.set_page_config(page_title="My Budget", layout="centered")
st.title("💰 My Mobile Budget")

# 2. Data Loading (The "Crash-Proof" Version)
csv_file = "my_budget_data.csv"
columns = ["Date", "Merchant", "Category", "Amount"]

# Check if file exists AND isn't empty
if os.path.exists(csv_file) and os.path.getsize(csv_file) > 0:
    try:
        df = pd.read_csv(csv_file)
    except Exception:
        # If the file is corrupted or unreadable, start fresh
        df = pd.DataFrame(columns=columns)
else:
    # If the file is missing or 0 bytes, create the structure
    df = pd.DataFrame(columns=columns)

# 3. Calculations
income = st.sidebar.number_input("Monthly Income ($)", min_value=0.0, value=5000.0)
total_spent = df['Amount'].sum() if not df.empty else 0.0
remaining = income - total_spent

col1, col2 = st.columns(2)
col1.metric("Remaining", f"${remaining:,.2f}")
col2.metric("Total Spent", f"${total_spent:,.2f}")

# 4. Input Form
st.divider()
with st.expander("➕ Log New Transaction", expanded=True):
    with st.form("entry_form", clear_on_submit=True):
        t_date = st.date_input("Date")
        t_merch = st.text_input("Merchant")
        t_cat = st.selectbox("Category", ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])
        t_amt = st.number_input("Amount ($)", min_value=0.0)
        
        if st.form_submit_button("Save Transaction", use_container_width=True):
            # Create a new line of data
            new_data = pd.DataFrame([[str(t_date), t_merch, t_cat, t_amt]], columns=columns)
            # Append it to the main table
            df = pd.concat([df, new_data], ignore_index=True)
            # Save it back to the file
            df.to_csv(csv_file, index=False)
            st.success("Saved!")
            st.rerun()

# 5. Display List
st.subheader("Recent Spending")
if not df.empty:
    # Shows newest transactions first
    st.table(df.iloc[::-1].head(10))
else:
    st.info("No transactions logged yet. Use the form above to start!")
