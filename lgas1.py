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
st.sidebar.info("Operations - Testing")

if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.selectbox(
    "Select Page",
    ["Dashboard", "Cylinder Finder", "Return & Penalty Log", "Add New Cylinder"]
)

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
        st.caption("**Rows in Grey indicate cylinders that have exceeded their safety test date.")
    else:
        st.warning("No data found.")
# 4. CYLINDER FINDER (Hardware Scanner Friendly)
elif page == "Cylinder Finder":
    st.title("🔍 Advanced Cylinder Search")
    
    colA, colB, colC = st.columns(3)
    with colA:
        s_id = st.text_input("Search ID").strip().upper()
    with colB:
        s_name = st.text_input("Search Customer")
    with colC:
        s_status = st.selectbox("Filter Status", ["All", "Full", "Empty", "Damaged"])

    f_df = df.copy()
    if s_id:
        f_df = f_df[f_df["Cylinder_ID"].str.upper().str.contains(s_id, na=False)]
    if s_name:
        f_df = f_df[f_df["Customer_Name"].str.contains(s_name, case=False, na=False)]
    if s_status != "All":
        f_df = f_df[f_df["Status"] == s_status]

    st.subheader(f"Results Found: {len(f_df)}")
    # hide_index=True removes the 0,1,2,3... column here as well
    st.dataframe(f_df, use_container_width=True, hide_index=True)

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

# 7. FOOTER
st.markdown("---")
last_time = st.session_state["last_refresh"]
footer_text = f"""
<div style="text-align: center; color: grey; font-size: 0.85em; font-family: sans-serif;">
    <p><b> Developed by </b> KWS </p>
    <p style="color: #007bff;"><b>Last Refresh:</b> {last_time} IST</p>
    <p> Cylinder Management System v1.2</p>
</div>
"""
st.markdown(footer_text, unsafe_allow_html=True)

























