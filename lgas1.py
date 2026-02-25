import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import time
from st_supabase_connection import SupabaseConnection

# 1. INITIALIZE & DB CONNECTION
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = "Initializing..."

conn = st.connection("supabase", type=SupabaseConnection)

@st.cache_data(ttl=60)
def load_supabase_data():
    try:
        response = conn.table("cylinders").select("*").execute()
        df = pd.DataFrame(response.data)
        ist = pytz.timezone('Asia/Kolkata')
        st.session_state["last_refresh"] = datetime.now(ist).strftime("%I:%M:%S %p")
        
        if not df.empty:
            # Ensure Location_PIN is a string for cleaner display
            df["Location_PIN"] = df["Location_PIN"].astype(str).str.strip()
            for col in ["Last_Fill_Date", "Last_Test_Date", "Next_Test_Due"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        st.session_state["last_refresh"] = "Refresh Error"
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame()

df = load_supabase_data()

# 2. SIDEBAR NAVIGATION
st.sidebar.title("Cylinder Management 2026")
st.sidebar.info("Operations - Domestic Gas Testing")

if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.selectbox("Select Page", [
    "Dashboard", 
    "Cylinder Finder", 
    "Bulk Operations",  # New Page
    "Add New Cylinder"
])

# 3. DASHBOARD PAGE
if page == "Dashboard":
    st.title("Live Fleet Dashboard")
    
    if not df.empty:
        # 1. Setup Dates
        ist = pytz.timezone('Asia/Kolkata')
        today = datetime.now(ist).date()

        # 2. Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Units", len(df))
        overdue_count = len(df[df["Next_Test_Due"].dt.date <= today])
        col2.metric("Overdue (Test)", overdue_count)
        col3.metric("Empty Stock", len(df[df["Status"] == "Empty"]))

        # 3. Style Function (Dark Grey / Near Black)
        def highlight_overdue(row):
            # Hex #1E1E1E is a soft "Onyx" grey close to black
            if row["Next_Test_Due"].date() <= today:
                return ['background-color: #303030; color: white; font-weight: italic'] * len(row)
            return [''] * len(row)

        styled_df = df.style.apply(highlight_overdue, axis=1)

        st.subheader("Inventory Overview")
        
        # 4. Display with Hidden Index
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # 5. Footer Note
        st.caption("**Grey Rows indicate cylinders that have exceeded their safety test date.")
    else:
        st.warning("No data found.")

# 4. CYLINDER FINDER (Hardware Scanner Friendly)
elif page == "Cylinder Finder":
    st.title("Advanced Cylinder Search")

    # 1. DEFINE THE CALLBACK
    def clear_callback():
        st.session_state["s_id_key"] = ""
        st.session_state["s_name_key"] = ""

    # 2. Initialize keys safely
    if "s_id_key" not in st.session_state:
        st.session_state["s_id_key"] = ""
    if "s_name_key" not in st.session_state:
        st.session_state["s_name_key"] = ""

    # 3. Search Inputs with Vertical Alignment
    # We use vertical_alignment="bottom" to line the button up with the boxes
    colA, colB, colC, colD = st.columns([3, 3, 2, 1], vertical_alignment="bottom")
    
    with colA:
        s_id = st.text_input("Search ID (Scan Now)", key="s_id_key").strip().upper()
    with colB:
        s_name = st.text_input("Search Customer", key="s_name_key").strip()
    with colC:
        s_status = st.selectbox("Filter Status", ["All", "Full", "Empty", "Damaged"])
    with colD:
        # The button will now sit perfectly level with the input fields
        st.button("Reset", on_click=clear_callback, use_container_width=True)

    # 4. Date Setup
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).date()

    # 5. Filtering Logic
    f_df = df.copy()
    if s_id:
        f_df = f_df[f_df["Cylinder_ID"].str.upper().str.contains(s_id, na=False)]
    if s_name:
        f_df = f_df[f_df["Customer_Name"].str.contains(s_name, case=False, na=False)]
    if s_status != "All":
        f_df = f_df[f_df["Status"] == s_status]

    # 6. Alert Logic (Only for ID or Name search)
    if s_id or s_name:
        if not f_df.empty:
            overdue_list = f_df[f_df["Next_Test_Due"].dt.date <= today]
            num_overdue = len(overdue_list)
            if num_overdue > 0:
                if s_id and num_overdue == 1:
                    due_date = overdue_list.iloc[0]["Next_Test_Due"].date()
                    st.error(f"⚠️ SAFETY ALERT: Cylinder {s_id} is OVERDUE! (Due: {due_date})")
                else:
                    st.error(f"⚠️ ATTENTION: Found {num_overdue} overdue cylinder(s) for your search.")
            else:
                st.success(f"✅ No overdue cylinders found for this search.")
        else:
            st.warning("No matching cylinders found.")

    # 7. Apply Dark-Grey Styling
    def highlight_overdue(row):
        if row["Next_Test_Due"].date() <= today:
            return ['background-color: #1E1E1E; color: #E0E0E0; font-weight: bold'] * len(row)
        return [''] * len(row)

    styled_f_df = f_df.style.apply(highlight_overdue, axis=1)

    st.subheader(f"Results Found: {len(f_df)}")
    st.dataframe(styled_f_df, use_container_width=True, hide_index=True)


#5a. BULK OPERATIONS (For High Volume 3,000+ Units) ---
# --- 5. BULK OPERATIONS (Final Integrated Version) ---
elif page == "Bulk Operations":
    st.title("🚛 Bulk Management & Progress")
    st.markdown("Track batch completion and perform high-volume updates.")

    # Initialize session state for the text area if it doesn't exist
    if "bulk_ids_val" not in st.session_state:
        st.session_state.bulk_ids_val = ""

    # 1. BATCH LOOKUP & PROGRESS BAR
    with st.container(border=True):
        col_lookup, col_pull = st.columns([3, 1])
        
        with col_lookup:
            batch_lookup = st.text_input("Enter Batch Number to Track", placeholder="e.g., Batch001")
        
        if batch_lookup:
            # Filter the main dataframe for this batch
            batch_data = df[df["Batch_ID"] == batch_lookup]
            
            if not batch_data.empty:
                total_in_batch = len(batch_data)
                # We define "Completed" as status being 'Full'
                completed = len(batch_data[batch_data["Status"] == "Full"])
                progress_percent = int((completed / total_in_batch) * 100)

                st.write(f"**Batch Progress:** {completed} of {total_in_batch} units tested/filled")
                st.progress(progress_percent / 100)
                st.caption(f"🏁 {progress_percent}% of this batch is ready.")

                with col_pull:
                    st.write(" ") # Spacer
                    if st.button("🔍 Pull IDs", use_container_width=True, help="Click to fill the scan box with all IDs in this batch"):
                        ids_to_pull = "\n".join(batch_data["Cylinder_ID"].astype(str).tolist())
                        st.session_state.bulk_ids_val = ids_to_pull
                        st.rerun()
            else:
                st.info("No cylinders found with that Batch ID.")

    st.divider()

    # 2. THE UPDATE FORM
    with st.expander("📝 Update Selected Batch", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # We pre-fill the batch number if the user searched for it above
            target_batch = st.text_input("Target Batch ID", value=batch_lookup if batch_lookup else "")
            new_location = st.selectbox("Move To", ["Testing Center", "Gas Company"])
        
        with col2:
            new_owner = st.text_input("Assign to Company/Customer")
            new_status = st.selectbox("Update Status", ["No Change", "Empty", "Full", "Damaged"])

        # Linked to session_state so the 'Pull IDs' button can fill it
        bulk_input = st.text_area(
            "Scan IDs (One per line)", 
            value=st.session_state.bulk_ids_val, 
            height=250
        )

        if st.button("🚀 Process Bulk Update", use_container_width=True):
            if bulk_input and target_batch:
                # Clean the input list
                id_list = [id.strip().upper() for id in bulk_input.replace(',', '\n').split('\n') if id.strip()]
                
                try:
                    # Construct the update
                    update_payload = {
                        "Current_Location": new_location,
                        "Batch_ID": target_batch
                    }
                    if new_owner:
                        update_payload["Customer_Name"] = new_owner
                    if new_status != "No Change":
                        update_payload["Status"] = new_status
                    
                    # Supabase Batch Update
                    supabase.table("cylinders").update(update_payload).in_("Cylinder_ID", id_list).execute()
                    
                    st.success(f"✅ Successfully updated {len(id_list)} cylinders!")
                    st.balloons()
                    
                    # Clear cache so the progress bar updates immediately
                    st.cache_data.clear()
                    # Optional: Clear the scan box after success
                    st.session_state.bulk_ids_val = "" 
                except Exception as e:
                    st.error(f"Database Error: {e}")
            else:
                st.warning("Please provide a Batch ID and at least one Cylinder ID.")



# 5. RETURN & PENALTY LOG
elif page == "Return & Penalty Log":
    st.title("Cylinder Return Audit")
    if not df.empty:
        # You can also scan into a selectbox if the ID matches exactly
        target_id = st.selectbox("Select ID for Return", options=df["Cylinder_ID"].unique())
        with st.form("audit_form"):
            condition = st.selectbox("Condition", ["Good", "Dented", "Leaking", "Valve Damage"])
            if st.form_submit_button("Submit Return"):
                new_status = "Empty" if condition == "Good" else "Damaged"
                try:
                    conn.table("cylinders").update({"Status": new_status, "Fill_Percent": 0}).eq("Cylinder_ID", target_id).execute()
                    st.success(f"Cylinder {target_id} processed!")
                    time.sleep(2)
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

# 6. ADD NEW CYLINDER (Hardware Scanner Friendly)
elif page == "Add New Cylinder":
    st.title("Register New Cylinder")
    
    # clear_on_submit=True is critical for scanners so you don't have to delete the old ID manually
    with st.form("new_entry_form", clear_on_submit=True):
        st.write("Scan the cylinder barcode to auto-fill ID.")
        c_id = st.text_input("New Cylinder ID").strip().upper()
        
        cust = st.text_input("Customer Name", value="Internal Stock")
        pin = st.text_input("Location PIN", value="500001", max_chars=6)
        
        cap_val = st.selectbox("Capacity (kg)", options=[5.0, 10.0, 14.2, 19.0, 47.5], index=2)
        
        if st.form_submit_button("Add Cylinder"):
            if not c_id:
                st.error("Missing Cylinder ID!")
            else:
                today = datetime.now().date()
                payload = {
                    "Cylinder_ID": str(c_id),
                    "Customer_Name": str(cust),
                    "Location_PIN": int(pin) if pin.isdigit() else 0,
                    "Capacity_kg": float(cap_val),
                    "Fill_Percent": 100,
                    "Status": "Full",
                    "Last_Fill_Date": str(today),
                    "Last_Test_Date": str(today),
                    "Next_Test_Due": str(today + pd.Timedelta(days=1825)),
                    "Overdue": False
                }
                try:
                    conn.table("cylinders").insert(payload).execute()
                    st.success(f"Cylinder {c_id} added successfully!")
                    time.sleep(2)
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Database Error: {e}")

# 7. FOOTER #JCNaga
st.markdown("---")
last_time = st.session_state["last_refresh"]
footer_text = f"""
<div style="text-align: center; color: grey; font-size: 0.85em; font-family: sans-serif;">
    <p><b> Developed for </b> KWS Pvt Ltd </p>
    <p style="color: #007bff;"><b>Last Refresh:</b> {last_time} IST</p>
    <p> Cylinder Management System v1.2</p>
</div>
"""
st.markdown(footer_text, unsafe_allow_html=True)












































