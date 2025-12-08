import streamlit as st
import mysql.connector
from datetime import datetime, date, time
from dataclasses import dataclass, field
from typing import List, Dict
import json
import math
import io
import pandas as pd

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# ==========================================
# CONFIGURATION
# ==========================================
KINGDOM_LOGO_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQMZ0z9WhWg9G_roekRq7BHmd08icwmjOl6Qg&s"

# ==========================================
# MYSQL DATABASE FUNCTIONS
# ==========================================
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            port=st.secrets["mysql"]["port"]
        )
    except Exception:
        return None

def load_sites_from_db(include_archived=False):
    conn = get_db_connection()
    if not conn: return {}
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT site_name, json_data FROM sites")
        results = cursor.fetchall()
        conn.close()
        
        sites = {}
        for row in results:
            data = row['json_data']
            if isinstance(data, str):
                data = json.loads(data)
            
            is_archived = data.get("archived", False)
            if not include_archived and is_archived:
                continue
                
            sites[row['site_name']] = data
        return sites
    except Exception:
        if conn: conn.close()
        return {}

def save_site_to_db(site_name, bid_object):
    conn = get_db_connection()
    if not conn: return False
    
    cursor = conn.cursor()
    data_dict = bid_object.to_dict()
    data_dict["archived"] = False 
    
    json_str = json.dumps(data_dict)
    
    query = """
    INSERT INTO sites (site_name, json_data) 
    VALUES (%s, %s) 
    ON DUPLICATE KEY UPDATE json_data = %s
    """
    try:
        cursor.execute(query, (site_name, json_str, json_str))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Save Failed: {e}")
        if conn: conn.close()
        return False

def toggle_archive_status(site_name, current_data, archive=True):
    conn = get_db_connection()
    if not conn: return False
    
    current_data["archived"] = archive
    json_str = json.dumps(current_data)
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE sites SET json_data = %s WHERE site_name = %s", (json_str, site_name))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Archive Failed: {e}")
        if conn: conn.close()
        return False

def delete_site_permanently(site_name):
    conn = get_db_connection()
    if not conn: return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sites WHERE site_name = %s", (site_name,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Delete Failed: {e}")
        if conn: conn.close()
        return False

# ==========================================
# DATA MODEL
# ==========================================
@dataclass
class EventBid:
    origin_kingdom: str = "Meridies"
    group_name: str = ""
    event_type: str = "Local"  
    event_name: str = ""
    bid_for_year: int = datetime.now().year
    
    site_name: str = ""
    site_address: str = ""
    start_date: date = date.today()
    start_time: time = time(17, 0)
    end_date: date = date.today()
    end_time: time = time(12, 0)
    gate_time: time = time(17, 0)
    is_single_day: bool = False
    
    event_stewards: List[str] = field(default_factory=lambda: ["", "", "", ""])
    feast_stewards: List[str] = field(default_factory=lambda: ["", "", ""])
    
    parking_spaces: int = 0
    bathrooms_count: int = 0
    ada_ramps: bool = False
    ada_parking: bool = False
    ada_parking_count: int = 0
    ada_bathrooms: bool = False
    ada_bathroom_count: int = 0

    kitchen_size: str = "None"
    kitchen_sq_ft: int = 0
    kitchen_stove_burners: int = 0
    kitchen_ovens: int = 0
    kitchen_3bay_sinks: int = 0
    kitchen_prep_tables: int = 0
    kitchen_garbage_cans: int = 0
    kitchen_fridge_household: int = 0
    kitchen_freezer_household: int = 0
    kitchen_amenities: List[str] = field(default_factory=list)

    camping_allowed: bool = False
    camping_tents: int = 0
    camping_rv: int = 0
    
    site_fee: float = 0.0 
    site_variable_cost: float = 0.0 
    
    ticket_weekend_member: float = 0.0
    ticket_daytrip_member: float = 0.0
    nms_surcharge: float = 10.0
    
    feast_fee: float = 0.0
    feast_cost_per_person: float = 0.0
    feast_capacity: int = 0
    
    beds_top_qty: int = 0
    beds_top_price: float = 0.0
    beds_bot_qty: int = 0
    beds_bot_price: float = 0.0

    expenses: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self):
        return json.loads(json.dumps(self, default=lambda o: o.isoformat() if isinstance(o, (date, time)) else o.__dict__))

    def load_data(self, data_dict: dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                if key in ["start_date", "end_date"] and isinstance(value, str):
                    try: setattr(self, key, date.fromisoformat(value))
                    except: pass
                elif key in ["start_time", "end_time", "gate_time"] and isinstance(value, str):
                    try: setattr(self, key, time.fromisoformat(value))
                    except: pass
                else:
                    setattr(self, key, value)

    def apply_site_profile(self, profile):
        if not profile: return
        site_keys = [
            "site_name", "site_address", "parking_spaces", "bathrooms_count",
            "camping_allowed", "camping_tents", "camping_rv",
            "kitchen_size", "kitchen_sq_ft", "kitchen_stove_burners",
            "kitchen_ovens", "kitchen_3bay_sinks", "kitchen_prep_tables",
            "kitchen_garbage_cans", "kitchen_fridge_household", "kitchen_freezer_household",
            "ada_ramps", "ada_parking", "ada_parking_count", "ada_bathrooms",
            "ada_bathroom_count", "site_fee", 
            "beds_top_qty", "beds_top_price", "beds_bot_qty", "beds_bot_price"
        ]
        for key in site_keys:
            if key in profile:
                setattr(self, key, profile[key])

    def get_total_fixed_costs(self, mode="projected"):
        ops_total = sum(item.get(mode, 0) for item in self.expenses.values())
        return self.site_fee + ops_total

    def calculate_projection(self, attend_weekend, attend_daytrip, feast_count, sold_top, sold_bot, mode="projected"):
        fixed_costs = self.get_total_fixed_costs(mode)
        
        rev_weekend = self.ticket_weekend_member * attend_weekend
        rev_daytrip = self.ticket_daytrip_member * attend_daytrip
        total_gate_revenue = rev_weekend + rev_daytrip
        
        total_attendees = attend_weekend + attend_daytrip
        total_variable = self.site_variable_cost * total_attendees
        
        gate_net = total_gate_revenue - fixed_costs - total_variable
        
        feast_rev = self.feast_fee * feast_count
        feast_exp = self.feast_cost_per_person * feast_count
        feast_net = feast_rev - feast_exp
        
        bed_rev = (self.beds_top_price * sold_top) + (self.beds_bot_price * sold_bot)
        bed_net = bed_rev
        
        total_net = gate_net + feast_net + bed_net
        
        margin = self.ticket_weekend_member - self.site_variable_cost
        
        if margin <= 0:
            if fixed_costs == 0 and margin == 0:
                break_even = 0 
            else:
                break_even = "Price < Variable Cost"
        else:
            break_even = math.ceil(fixed_costs / margin)

        if total_attendees > 0:
            target_be_price = (fixed_costs / total_attendees) + self.site_variable_cost
        else:
            target_be_price = 0.0

        return {
            "total_attendees": total_attendees,
            "total_revenue": total_gate_revenue + feast_rev + bed_rev,
            "total_expense": fixed_costs + total_variable + feast_exp,
            "gate_net": gate_net,
            "feast_net": feast_net,
            "bed_net": bed_net,
            "total_net": total_net,
            "break_even": break_even,
            "target_be_price": target_be_price
        }

# ==========================================
# PDF GENERATION LOGIC
# ==========================================
def export_to_pdf(bid: EventBid, projection: dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    elements = []
    
    elements.append(Paragraph("Kingdom of Meridies Event Bid", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>Event:</b> {bid.event_name} ({bid.event_type})", styles["Normal"]))
    elements.append(Paragraph(f"<b>Location:</b> {bid.site_name} - {bid.site_address}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("<b>Kitchen Facilities</b>", styles["Heading3"]))
    k_text = f"Size: {bid.kitchen_size} ({bid.kitchen_sq_ft} sq ft)<br/>"
    k_text += f"Equip: {bid.kitchen_stove_burners} Burners, {bid.kitchen_ovens} Ovens<br/>"
    k_text += f"Prep: {bid.kitchen_3bay_sinks} Sinks, {bid.kitchen_prep_tables} Tables<br/>"
    k_text += f"Household Cold: {bid.kitchen_fridge_household} Fridges, {bid.kitchen_freezer_household} Freezers"
    elements.append(Paragraph(k_text, styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("<b>Gate Pricing</b>", styles["Heading3"]))
    p_text = f"Weekend Member: ${bid.ticket_weekend_member:.2f} (Non-Member: ${bid.ticket_weekend_member + bid.nms_surcharge:.2f})<br/>"
    p_text += f"Daytrip Member: ${bid.ticket_daytrip_member:.2f} (Non-Member: ${bid.ticket_daytrip_member + bid.nms_surcharge:.2f})<br/>"
    p_text += f"NMS Surcharge: ${bid.nms_surcharge:.2f}"
    elements.append(Paragraph(p_text, styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Lodging Stats</b>", styles["Heading3"]))
    l_text = f"Top Bunks: {bid.beds_top_qty} (${bid.beds_top_price:.2f})<br/>"
    l_text += f"Bottom Bunks: {bid.beds_bot_qty} (${bid.beds_bot_price:.2f})"
    elements.append(Paragraph(l_text, styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph("<b>Financial Projection</b>", styles["Heading3"]))
    
    be_val = projection['break_even']
    be_str = f"{be_val} Attendees" if isinstance(be_val, (int, float)) else str(be_val)

    data = [
        ["Category", "Amount"],
        ["Total Revenue", f"${projection['total_revenue']:.2f}"],
        ["Total Expense", f"${projection['total_expense']:.2f}"],
        ["NET PROFIT", f"${projection['total_net']:.2f}"],
        ["Gate Break Even", be_str]
    ]
    t = Table(data, colWidths=[200, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,-2), (-1,-1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    
    # Add Expense Breakdown to PDF as well
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("<b>Operational Expenses</b>", styles["Heading3"]))
    
    exp_data = [["Item", "Projected Cost"]]
    for item, val in bid.expenses.items():
        exp_data.append([item, f"${val['projected']:.2f}"])
    
    if len(exp_data) > 1:
        t_exp = Table(exp_data, colWidths=[250, 100])
        t_exp.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))
        elements.append(t_exp)
    else:
        elements.append(Paragraph("No operational expenses listed.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# STREAMLIT GUI
# ==========================================
def main():
    st.set_page_config(page_title="Meridies Bidder", layout="wide", page_icon=KINGDOM_LOGO_URL)
    
    # Initialize Session State
    if "bid" not in st.session_state:
        st.session_state.bid = EventBid()
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
        
    bid = st.session_state.bid

    col_logo, col_title = st.columns([1, 6])
    with col_logo: st.image(KINGDOM_LOGO_URL, width=80)
    with col_title: 
        st.title("Kingdom of Meridies Event Bidder")
        role = "Admin Mode" if st.session_state.is_admin else "Public Mode"
        st.caption(f"Budgeting Tool • {role}")

    # --- SIDEBAR: AUTH & DATABASE ---
    with st.sidebar:
        # LOGIN SECTION
        if not st.session_state.is_admin:
            with st.expander("🔐 Admin Login", expanded=True):
                admin_pass = st.text_input("Password", type="password")
                if st.button("Login"):
                    correct_pass = st.secrets["general"]["admin_password"] if "general" in st.secrets else "Meridies2024"
                    if admin_pass == correct_pass:
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("Incorrect Password")
        else:
            if st.button("🔓 Log Out"):
                st.session_state.is_admin = False
                st.rerun()
            st.success("You are logged in as Admin.")
            st.markdown("---")

        st.header("📂 Database")
        
        # Load Sites logic (Always visible)
        available_sites = load_sites_from_db(include_archived=st.session_state.is_admin)
        
        if not available_sites:
            available_sites = {"Select a Site...": None}
            if get_db_connection():
                st.info("Database empty.")
            else:
                st.warning("Database Disconnected.")
        
        options = ["Select a Site..."] + list(available_sites.keys())
        site_choice = st.selectbox("Load Known Site", options)
        
        if site_choice and site_choice != "Select a Site...":
            if st.button("Load Site Data"):
                bid.apply_site_profile(available_sites[site_choice])
                st.success(f"Loaded {site_choice}")
        
        st.divider()
        uploaded = st.file_uploader("Upload Bid JSON", type="json")
        if uploaded:
            data = json.load(uploaded)
            bid.load_data(data)
            st.success("Bid JSON Loaded")

    # --- MAIN FORM (Calculator) ---
    
    st.subheader("1. Event Details")
    c1, c2 = st.columns(2)
    bid.event_name = c1.text_input("Event Name", bid.event_name)
    bid.event_type = c2.selectbox("Type", ["Local", "Kingdom"], index=0 if bid.event_type=="Local" else 1)
    d1, d2, d3 = st.columns(3)
    bid.start_date = d1.date_input("Start Date", bid.start_date)
    bid.end_date = d2.date_input("End Date", bid.end_date)
    bid.is_single_day = d3.checkbox("Single Day Event?", bid.is_single_day)

    st.subheader("2. Staffing")
    s1, s2 = st.columns(2)
    with s1:
        st.caption("Event Stewards")
        for i in range(2): bid.event_stewards[i] = st.text_input(f"Autocrat {i+1}", bid.event_stewards[i], key=f"es{i}")
    with s2:
        st.caption("Feast Stewards")
        for i in range(2): bid.feast_stewards[i] = st.text_input(f"Feastcrat {i+1}", bid.feast_stewards[i], key=f"fs{i}")

    st.markdown("---")
    st.subheader("3. Site Facilities")
    with st.expander("Kitchen Specs", expanded=True):
        k1, k2, k3, k4 = st.columns(4)
        bid.kitchen_size = k1.selectbox("Kitchen Size", ["None", "Small", "Medium", "Large"], index=0)
        bid.kitchen_sq_ft = k2.number_input("Sq Ft", value=int(bid.kitchen_sq_ft), step=10)
        bid.kitchen_stove_burners = k3.number_input("Burners", value=int(bid.kitchen_stove_burners), step=1)
        bid.kitchen_ovens = k4.number_input("Ovens", value=int(bid.kitchen_ovens), step=1)
        k5, k6, k7 = st.columns(3)
        bid.kitchen_3bay_sinks = k5.number_input("3-Bay Sinks", value=int(bid.kitchen_3bay_sinks), step=1)
        bid.kitchen_prep_tables = k6.number_input("Prep Tables", value=int(bid.kitchen_prep_tables), step=1)
        bid.kitchen_garbage_cans = k7.number_input("Garbage Cans", value=int(bid.kitchen_garbage_cans), step=1)
        st.caption("Household Cold Storage")
        k8, k9 = st.columns(2)
        bid.kitchen_fridge_household = k8.number_input("Household Fridges", value=int(bid.kitchen_fridge_household), step=1)
        bid.kitchen_freezer_household = k9.number_input("Household Freezers", value=int(bid.kitchen_freezer_household), step=1)

    with st.expander("ADA & Accessibility", expanded=False):
        a1, a2, a3 = st.columns(3)
        bid.ada_ramps = a1.checkbox("Ramps Available", bid.ada_ramps)
        bid.ada_parking = a2.checkbox("ADA Parking", bid.ada_parking)
        bid.ada_bathrooms = a3.checkbox("ADA Bathrooms", bid.ada_bathrooms)
        a4, a5 = st.columns(2)
        bid.ada_parking_count = a4.number_input("Count of ADA Spots", value=int(bid.ada_parking_count), step=1)
        bid.ada_bathroom_count = a5.number_input("Count of ADA Stalls", value=int(bid.ada_bathroom_count), step=1)

    st.markdown("---")
    st.subheader("4. Financials")
    f1, f2, f3 = st.columns(3)
    bid.site_fee = f1.number_input("Site Rental Fee (Fixed)", value=float(bid.site_fee), min_value=0.0, step=10.0)
    bid.site_variable_cost = f2.number_input("Per Person Site Cost", value=float(bid.site_variable_cost), min_value=0.0, step=0.5)
    bid.nms_surcharge = f3.number_input("Non-Member Surcharge (NMS)", value=float(bid.nms_surcharge), min_value=0.0, step=1.0)
    
    gp1, gp2, gp3, gp4 = st.columns(4)
    bid.ticket_weekend_member = gp1.number_input("Adult Member Price", value=float(bid.ticket_weekend_member), min_value=0.0, step=1.0)
    gp2.metric("Adult Non-Member", f"${bid.ticket_weekend_member + bid.nms_surcharge:.2f}")
    bid.ticket_daytrip_member = gp3.number_input("Daytrip Member Price", value=float(bid.ticket_daytrip_member), min_value=0.0, step=1.0)
    gp4.metric("Daytrip Non-Member", f"${bid.ticket_daytrip_member + bid.nms_surcharge:.2f}")
    
    st.caption("Feast & Beds (Siloed Costs)")
    fb1, fb2, fb3 = st.columns(3)
    bid.feast_fee = fb1.number_input("Feast Ticket Price", value=float(bid.feast_fee), min_value=0.0, step=1.0)
    bid.feast_cost_per_person = fb2.number_input("Feast Food Cost", value=float(bid.feast_cost_per_person), min_value=0.0, step=0.5)
    bid.feast_capacity = fb3.number_input("Feast Max Cap.", value=int(bid.feast_capacity), step=1)
    
    st.write("**Cabin / Lodging Configuration**")
    b1, b2, b3, b4 = st.columns(4)
    bid.beds_top_qty = b1.number_input("Qty: Top Bunks", value=int(bid.beds_top_qty), step=1)
    bid.beds_top_price = b2.number_input("Price: Top ($)", value=float(bid.beds_top_price), min_value=0.0, step=1.0)
    bid.beds_bot_qty = b3.number_input("Qty: Bottom Bunks", value=int(bid.beds_bot_qty), step=1)
    bid.beds_bot_price = b4.number_input("Price: Bottom ($)", value=float(bid.beds_bot_price), min_value=0.0, step=1.0)

    # 5. EXPENSES SECTION (FIXED)
    st.markdown("---")
    st.subheader("5. Operational Expenses")
    
    # Callback function to add item and clear inputs
    def add_expense_callback():
        # Get values from session state
        name = st.session_state["new_exp_name_input"]
        cost = st.session_state["new_exp_cost_input"]
        
        if name:
            # Add to bid object
            st.session_state.bid.expenses[name] = {"projected": cost, "actual": 0.0}
            # Clear inputs by resetting session state keys
            st.session_state["new_exp_name_input"] = ""
            st.session_state["new_exp_cost_input"] = 0.0

    # Input columns
    e_col1, e_col2, e_col3 = st.columns([2, 1, 1])
    e_col1.text_input("New Expense Item", key="new_exp_name_input")
    e_col2.number_input("Cost", min_value=0.0, step=10.0, key="new_exp_cost_input")
    e_col3.button("Add Expense", on_click=add_expense_callback)

    # Display List
    if bid.expenses:
        st.markdown("##### Current Budget Items:")
        # Convert to DataFrame for cleaner display
        exp_list = [{"Item": k, "Projected Cost": f"${v['projected']:.2f}"} for k, v in bid.expenses.items()]
        st.dataframe(pd.DataFrame(exp_list), use_container_width=True, hide_index=True)

    # 6. Results & 7. Exports (Standard)
    st.markdown("---")
    st.subheader("📊 Projections")
    p1, p2, p3 = st.columns(3)
    proj_wk = p1.number_input("Proj. Weekend Heads", value=100, step=10)
    proj_dt = p2.number_input("Proj. Daytrip Heads", value=20, step=5)
    proj_fst = p3.number_input("Proj. Feast Eaters", value=50, step=5)
    p4, p5 = st.columns(2)
    sold_top = p4.number_input(f"Proj. Top Beds Sold (Max {bid.beds_top_qty})", value=0, max_value=max(0, bid.beds_top_qty), step=1)
    sold_bot = p5.number_input(f"Proj. Bot Beds Sold (Max {bid.beds_bot_qty})", value=0, max_value=max(0, bid.beds_bot_qty), step=1)
    
    results = bid.calculate_projection(proj_wk, proj_dt, proj_fst, sold_top, sold_bot)
    
    if results['target_be_price'] > 0:
        st.info(f"💡 **Target Price:** To exactly break even with {results['total_attendees']} attendees, your Member Ticket Price must be at least: **${results['target_be_price']:.2f}**")

    r1, r2, r3 = st.columns(3)
    r1.metric("Net Profit", f"${results['total_net']:.2f}")
    r2.metric("Break Even (Gate)", results['break_even'])
    r3.metric("Total Expenses", f"${results['total_expense']:.2f}")
    
    with st.expander("Detailed Financial Breakdown"):
        st.json(results)

    st.markdown("---")
    st.subheader("💾 Save & Submit")
    ex1, ex2, ex3 = st.columns(3)
    pdf_bytes = export_to_pdf(bid, results)
    ex1.download_button("Download PDF Report", pdf_bytes, "bid_report.pdf", "application/pdf")
    json_str = json.dumps(bid.to_dict(), indent=4)
    ex2.download_button("Download Save File (.json)", json_str, "bid_save.json", "application/json")
    flat_data = bid.__dict__.copy()
    if "expenses" in flat_data: del flat_data["expenses"] 
    df = pd.DataFrame([flat_data])
    csv = df.to_csv(index=False).encode('utf-8')
    ex3.download_button("Download CSV (For Sheets)", csv, "bid_spreadsheet.csv", "text/csv")

    # ==========================================
    # ADMIN SECTIONS
    # ==========================================
    if st.session_state.is_admin:
        st.markdown("---")
        st.header("👑 Admin Controls")
        st.info("You are in Admin Mode. You can Save, Archive, and Delete sites.")

        with st.expander("☁️ Save/Update Current Site", expanded=True):
            db_key_name = st.text_input("Site Name to Save As (Unique)", bid.site_name)
            if st.button("Save Site to Database"):
                if not db_key_name.strip():
                    st.error("⚠️ Site Name required.")
                else:
                    if save_site_to_db(db_key_name, bid):
                        st.success(f"Saved '{db_key_name}'!")
                        st.cache_data.clear()
                        st.rerun()

        with st.expander("🗑️ Manage Existing Sites"):
            all_sites = load_sites_from_db(include_archived=True)
            if not all_sites:
                st.write("No sites to manage.")
            else:
                manage_choice = st.selectbox("Select Site to Manage", list(all_sites.keys()))
                selected_data = all_sites[manage_choice]
                
                is_archived = selected_data.get("archived", False)
                status_text = "🔴 ARCHIVED (Hidden)" if is_archived else "🟢 ACTIVE (Visible)"
                st.markdown(f"**Current Status:** {status_text}")
                
                mc1, mc2 = st.columns(2)
                btn_label = "Un-Archive (Make Visible)" if is_archived else "Archive (Hide Site)"
                
                if mc1.button(btn_label):
                    if toggle_archive_status(manage_choice, selected_data, archive=not is_archived):
                        st.success("Status updated.")
                        st.cache_data.clear()
                        st.rerun()
                
                if mc2.button("❌ DELETE PERMANENTLY"):
                    if delete_site_permanently(manage_choice):
                        st.success("Deleted.")
                        st.cache_data.clear()
                        st.rerun()

if __name__ == "__main__":
    main()
