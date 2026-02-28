import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# 1. Page Config
st.set_page_config(page_title="EveryDollar Clone", layout="centered")

# --- STATE MANAGEMENT (Time Travel) ---
if 'view_date' not in st.session_state:
    st.session_state.view_date = datetime.date.today().replace(day=1)

def change_month(months_to_add):
    new_month = st.session_state.view_date.month - 1 + months_to_add
    new_year = st.session_state.view_date.year + new_month // 12
    new_month = new_month % 12 + 1
    st.session_state.view_date = datetime.date(new_year, new_month, 1)

# 2. Establish Secure Connection (Integrity foundation)
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Use robust method to maintain Integrity and prevent failures like before
    df = conn.read(ttl=0)
except Exception as e:
    # Authorization error check is crucial for preserving Integrity
    st.error(f"Waiting for secure handshake... Ensure service account key is correctly set in Secrets and that email has Editor permissions. Error: {e}")
    df = pd.DataFrame(columns=["Date", "Type", "Merchant", "Category", "Amount"]) # Expanded columns

# --- MODALS (Quick Add with Toggle & Native Look) ---
@st.dialog("➕ Add Transaction")
def transaction_modal():
    with st.form("entry_form", clear_on_submit=True):
        
        # New Segmented Expense/Income Toggle (Replicating looks)
        tx_type = st.radio(
            "Transaction Type",
            ["- Expense", "+ Income"],
            horizontal=True,
            label_visibility="collapsed" # Hide the internal label for a clean segmented-control look
        )
        
        st.divider()

        # Replicate field structure from the photo
        
        # 1. Date Field
        t_date = st.date_input("Date", value=st.session_state.view_date)
        
        # 2. Amount Field with Numeric Pad detail (Triggers system-level dial-pad on mobile)
        t_amt = st.number_input("Amount ($)", min_value=0.00, value=0.00, step=0.01)
        
        # 3. Merchant Field (New from previous turn, replicated from image)
        t_merch = st.text_input("Merchant", placeholder="Enter Name")
        
        # 4. Budget Item Selector (Using current categories for now, keeping Select > placeholder logic)
        # The prompt asks for this function, so I'm including the custom logic
        t_cat = st.selectbox("Budget Item(s)", ["Select >"] + ["Housing", "Food", "Soccer", "Auto", "Savings", "Other"])

        st.divider()

        # Preserve previous robust save logic that maintains integrity
        if st.form_submit_button("Securely Sync Transaction", use_container_width=True):
            if t_merch and t_amt > 0 and t_cat != "Select >":
                # Extract type string: "Expense" or "Income"
                clean_type = tx_type.split(" ")[1]
                
                # Integrity: ensure only authorized write actions are attempted
                try:
                    new_row = pd.DataFrame([[str(t_date), clean_type, t_merch, t_cat, t_amt]], columns=df.columns)
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success("✅ Transaction Permanently Saved!")
                    st.rerun()
                except Exception as e:
                    # Capture authorization errors explicitly to maintain data Integrity
                    st.error(f"Secure handshake failed. Write unauthorized. Please check service account email permission as Editor. Error: {e}")
            else:
                st.warning("Please complete Date, Amount, Merchant, and Budget Item before saving.")

# --- DATA FILTERING ---
current_month_str = st.session_state.view_date.strftime("%B %Y")
filtered_df = df.copy()
if not filtered_df.empty:
    filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
    mask = (filtered_df['Date'].dt.month == st.session_state.view_date.month) & \
           (filtered_df['Date'].dt.year == st.session_state.view_date.year)
    filtered_df = filtered_df[mask]

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
tab_budget, tab_transactions = st.tabs(["📊 Budget", "💳 Transactions"])

# ==========================================
# 📊 VIEW 1: THE BUDGET TAB
# ==========================================
with tab_budget:
    # For now keeping basic, we need to build the "Income/Planned" logic soon!
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
    st.subheader(f"History for {current_month_str}")
    if not filtered_df.empty:
        # Format the date nicely before displaying
        display_df = filtered_df.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        
        # Apply conditional row coloring to entire rows (Integrity check by category)
        def color_income_rows(df):
            # Define a styling function to apply text color green for whole rows of type Income
            # Expense and all other rows are black/gray.
            def style_rows(row):
                if row.Type == 'Income':
                    return ['color: green' for _ in row]
                else:
                    return ['color: black' for _ in row]
            
            # Use Pandas Styler to apply row-level styling
            return df.style.apply(style_rows, axis=1)

        styled_df = color_income_rows(display_df.iloc[::-1].head(10))
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.write("No transactions logged for this month yet.")
