if st.form_submit_button("Save to Google Sheets", use_container_width=True):
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
