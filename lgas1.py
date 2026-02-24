import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import time  # New import for the delay
from st_supabase_connection import SupabaseConnection

# ────────────────────────────────────────────────
# 1. INITIALIZE SESSION STATE
# ────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = "Initializing..."

# ────────────────────────────────────────────────
# 2. DATABASE CONNECTION & LOADING
# ────────────────────────────────────────────────
conn = st.connection("supabase", type=SupabaseConnection)

@st.cache_data(ttl=60)
def load_supabase_data():
    try:
        response = conn.table("cylinders").select("*").execute()
        df = pd.DataFrame(response.data)
        
        # Capture current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        ist_now = datetime.now(ist)
        st.session_state["last_refresh"] = ist_now.strftime("%I:%M:%S %p")
        
        if not df.empty:
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

# ────────────────────────────────────────────────
# 3. SIDEBAR NAVIGATION
# ────────────────────────────────────────────────
st.sidebar.title("Gas Cylinder Management 2026")
st.sidebar.info("Operational Hub - Hyderabad")

if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.selectbox(
    "Select Page",
    ["Dashboard", "Cylinder Finder", "Return & Penalty Log", "Add New Cylinder"]
)

# ────────────────────────────────────────────────
# 4. DASHBOARD PAGE
# ────────────────────────────────────────────────
if page == "Dashboard":
    st.title("Live Fleet Dashboard")
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Units", len(df))
        overdue_count = df["Overdue"].sum() if "Overdue" in df.columns else 0
        col2.metric("Overdue (Test)", overdue_count)
        col3.metric("Empty Stock", len(df[df["Status"] == "Empty"]))
        
        st.subheader("Full Inventory Overview")
        st.dataframe(df.sort_values("Next_Test_Due"), use_container_width=True)

# ────────────────────────────────────────────────
# 5. CYLINDER FINDER (With Search Notification)
# ────────────────────────────────────────────────
elif page == "Cylinder Finder":
    st.title("🔍 Advanced Cylinder Search")
    
    colA, colB, colC = st.columns(3)
    with colA:
        s_id = st.text_input("Search ID", placeholder="LEO-XXX")
    with colB:
        s_name = st.text_input("Search Customer", placeholder="e.g. Hyderabad Gas")
    with colC:
        s_status = st.selectbox("Filter Status", ["All", "Full", "Empty", "Damaged"])

    f_df = df.copy()
    if s_id:
        f_df = f_df[f_df["Cylinder_ID"].str.contains(s_id, case=False, na=False)]
    if s_name:
        f_df = f_df[f_df["Customer_Name"].str.contains(s_name, case=False, na=False)]
    if s_status != "All":
        f_df = f_df[f_df["Status"] == s_status]

    if s_id or s_name or s_status != "All":
        st.toast(f"Filters applied. Found {len(f_df)} matches.", icon="🔍")

    st.subheader(f"Results Found: {len(f_df)}")
    st.dataframe(f_df, use_container_width=True)

# ────────────────────────────────────────────────
# 6. RETURN & PENALTY LOG (With 2-Second Delay)
# ────────────────────────────────────────────────
elif page == "Return & Penalty Log":
    st.title("Cylinder Return Audit")
    if not df.empty:
        target_id = st.selectbox("Select ID for Return", options=df["Cylinder_ID"].unique())
        with st.form("audit_form"):
            condition = st.selectbox("Condition", ["Good", "Dented", "Leaking", "Valve Damage"])
            if st.form_submit_button("Submit Return"):
                new_status = "Empty" if condition == "Good" else "Damaged"
                try:
                    conn.table("cylinders").update({"Status": new_status, "Fill_Percent": 0}).eq("Cylinder_ID", target_id).execute()
                    
                    # FIXED: Success message with delay
                    st.success(f"Cylinder {target_id} processed as {new_status}!")
                    time.sleep(2) 
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

# ────────────────────────────────────────────────
# 7. ADD NEW CYLINDER (With 2-Second Delay)
# ────────────────────────────────────────────────
elif page == "Add New Cylinder":
    st.title("Register New Stock")
    with st.form("new_entry_form"):
        c_id = st.text_input("New Cylinder ID")
        cust = st.text_input("Customer Name")
        pin = st.text_input("Location PIN (Numbers Only)", max_chars=6)
        cap_val = st.selectbox("Capacity (kg)", options=[5.0, 10.0, 14.2, 19.0, 47.5], index=2)
        
        if st.form_submit_button("Add Cylinder"):
            if not c_id:
                st.error("Please enter a Cylinder ID.")
            else:
                today = datetime.now().date()
                next_due = today + pd.Timedelta(days=1825)
                payload = {
                    "Cylinder_ID": str(c_id), "Customer_Name": str(cust),
                    "Location_PIN": int(pin) if pin.isdigit() else 0,
                    "Capacity_kg": float(cap_val), "Fill_Percent": 100,
                    "Status": "Full", "Last_Fill_Date": str(today),
                    "Last_Test_Date": str(today), "Next_Test_Due": str(next_due),
                    "Overdue": False
                }
                try:
                    conn.table("cylinders").insert(payload).execute()
                    
                    # FIXED: Success message with delay
                    st.success(f"Cylinder {c_id} ({cap_val}kg) added!")
                    time.sleep(2)
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Database Error: {e}")

# ────────────────────────────────────────────────
# 8. ENHANCED FOOTER (IST Timezone)
# ────────────────────────────────────────────────
st.markdown("---")
last_time = st.session_state["last_refresh"]
footer_text = f"""
<div style="text-align: center; color: grey; font-size: 0.85em; font-family: sans-serif;">
    <p><b>Project:</b> Domestic Gas Project | <b>Developed by:</b> KWS </p>
    <p><b>Softwares:</b> Streamlit, Supabase, Python, GitHub</p>
    <p style="color: #007bff;"><b>Last Cloud Refresh:</b> {last_time} IST</p>
    <p>© 2026 LeoGas Management System • v.1.4</p>
</div>
"""
st.markdown(footer_text, unsafe_allow_html=True)










