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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
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
            if isinstance(data, str): data = json.loads(data)
            if not include_archived and data.get("archived", False): continue
            sites[row['site_name']] = data
        return sites
    except Exception:
        if conn: conn.close()
        return {}

def save_site_to_db(site_name, bid_object):
    conn = get_db_connection()
    if not conn: return False
    
    # FILTER DATA: Only save SITE info, not EVENT info (privacy)
    full_data = bid_object.to_dict()
    
    # Define keys that belong to the SITE, not the EVENT
    site_keys = [
        "site_name", "site_address", "site_contact_name", "site_contact_info", "max_capacity",
        "ada_ramps", "ada_ramps_count", "ada_showers", "ada_showers_count", 
        "ada_bathrooms", "ada_bathrooms_count", "ada_parking", "ada_parking_count", "ada_comment",
        "showers_count", "bathrooms_count", "ground_fires", "ground_fires_restrictions", "alcohol_policy",
        "camping_modern", "camping_period", 
        "cabins_total_beds", "cabins_top_bunks", "cabins_bot_bunks", "cabins_per_cabin",
        "classrooms", "fighting_indoors", "fighting_outdoors", "equestrian_area", "parking_comment",
        "feast_hall_indoor", "feast_pavilion_outdoor",
        "kitchen_access", "kitchen_sq_ft", "kitchen_burners", "kitchen_ovens", "kitchen_sinks", "kitchen_prep_tables",
        "kitchen_hobart", "kitchen_warming_table", "kitchen_walkin_fridge", "kitchen_walkin_freezer",
        "kitchen_household_fridge_count", "kitchen_household_freezer_count", "kitchen_ice_maker",
        "site_cost", "site_deposit_refundable", "top_bunk_cost", "bot_bunk_cost"
    ]
    
    # Create a clean dictionary with only site data
    site_data = {k: full_data.get(k) for k in site_keys}
    site_data["archived"] = False
    
    json_str = json.dumps(site_data)
    
    try:
        cursor = conn.cursor()
        query = "INSERT INTO sites (site_name, json_data) VALUES (%s, %s) ON DUPLICATE KEY UPDATE json_data = %s"
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
    except Exception:
        conn.close()
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
    except Exception:
        conn.close()
        return False

# ==========================================
# DATA MODEL
# ==========================================
@dataclass
class EventBid:
    # --- EVENT HEADER ---
    group_name: str = ""
    event_name: str = ""
    event_type: str = "Local" # Kingdom or Local
    kingdom_event_type: str = "" # specific dropdown if Kingdom
    start_date: date = date.today()
    end_date: date = date.today()
    is_single_day: bool = False
    
    # Staff (Names + Private Contact Info)
    # Stored as list of dicts or strings
    group_seneschal_name: str = ""
    group_seneschal_contact: str = ""
    reservationist_name: str = ""
    reservationist_contact: str = ""
    
    event_stewards: List[Dict] = field(default_factory=lambda: [{"name": "", "contact": ""} for _ in range(2)])
    feast_stewards: List[Dict] = field(default_factory=lambda: [{"name": "", "contact": ""} for _ in range(2)])

    # --- SITE INFO ---
    site_name: str = ""
    site_address: str = ""
    site_contact_name: str = ""
    site_contact_info: str = ""
    max_capacity: int = 0
    
    # --- AMENITIES ---
    # ADA
    ada_ramps: bool = False
    ada_ramps_count: int = 0
    ada_showers: bool = False
    ada_showers_count: int = 0
    ada_bathrooms: bool = False
    ada_bathrooms_count: int = 0
    ada_parking: bool = False
    ada_parking_count: int = 0
    ada_comment: str = ""
    
    # General
    showers_count: int = 0
    bathrooms_count: int = 0
    ground_fires: bool = False
    ground_fires_restrictions: str = ""
    alcohol_policy: str = "Dry" # Dry, Wet, Discreetly Wet
    
    camping_modern: bool = False
    camping_period: bool = False
    
    # Cabins
    cabins_available: bool = False
    cabins_total_beds: int = 0
    cabins_top_bunks: int = 0
    cabins_bot_bunks: int = 0
    cabins_per_cabin: int = 0
    
    # Classrooms (List of dicts: [{"capacity": 30, "av": True}])
    classrooms: List[Dict] = field(default_factory=list)
    
    # Areas
    fighting_indoors: bool = False
    fighting_outdoors: bool = False
    equestrian_area: bool = False
    parking_comment: str = ""
    feast_hall_indoor: bool = False
    feast_pavilion_outdoor: bool = False
    
    # Kitchen
    kitchen_access: bool = False
    kitchen_sq_ft: int = 0
    kitchen_burners: int = 0
    kitchen_ovens: int = 0
    kitchen_sinks: int = 0
    kitchen_prep_tables: int = 0
    kitchen_hobart: bool = False
    kitchen_warming_table: bool = False
    kitchen_walkin_fridge: bool = False
    kitchen_walkin_freezer: bool = False
    kitchen_household_fridge_count: int = 0
    kitchen_household_freezer_count: int = 0
    kitchen_ice_maker: bool = False
    
    # --- EXPENSES (Budget vs Actual) ---
    site_deposit: float = 0.0
    site_deposit_refundable: bool = False
    site_deposit_deadline: str = ""
    
    site_cost: float = 0.0 # Rent minus deposit
    
    # Standard Budget Items
    budget_tokens: float = 0.0
    actual_tokens: float = 0.0
    
    budget_decor: float = 0.0
    actual_decor: float = 0.0
    
    budget_booklet: float = 0.0
    actual_booklet: float = 0.0
    
    budget_prizes: float = 0.0
    actual_prizes: float = 0.0
    
    # Dynamic Additional Lines [{"item": "Name", "budget": 0.0, "actual": 0.0}]
    additional_expenses: List[Dict] = field(default_factory=list)
    
    # --- INCOME ---
    nms_surcharge: float = 10.0
    daytrip_cost: float = 0.0
    weekend_cost: float = 0.0
    
    feast_cost_per_person: float = 0.0
    feast_seats: int = 0
    
    top_bunk_cost: float = 0.0
    bot_bunk_cost: float = 0.0
    
    # --- PROJECTIONS ---
    proj_attendees: int = 100
    proj_feast_sold: int = 50
    proj_top_sold: int = 0
    proj_bot_sold: int = 0

    def to_dict(self):
        return json.loads(json.dumps(self, default=lambda o: o.isoformat() if isinstance(o, (date, time)) else o.__dict__))

    def load_data(self, data: dict):
        for k, v in data.items():
            if hasattr(self, k):
                if k in ["start_date", "end_date"] and isinstance(v, str):
                    try: setattr(self, k, date.fromisoformat(v))
                    except: pass
                else:
                    setattr(self, k, v)

    def apply_site_profile(self, profile):
        if not profile: return
        for k, v in profile.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def calculate_financials(self):
        # 1. EXPENSES
        total_budget_expense = self.site_cost + self.budget_tokens + self.budget_decor + self.budget_booklet + self.budget_prizes
        total_actual_expense = self.site_cost + self.actual_tokens + self.actual_decor + self.actual_booklet + self.actual_prizes
        
        for line in self.additional_expenses:
            total_budget_expense += float(line.get("budget", 0.0))
            total_actual_expense += float(line.get("actual", 0.0))
            
        feast_budget_expense = self.feast_cost_per_person * self.proj_feast_sold
        
        # 2. INCOME
        gate_income = (self.weekend_cost * self.proj_attendees)
        lodging_income = (self.top_bunk_cost * self.proj_top_sold) + (self.bot_bunk_cost * self.proj_bot_sold)
        
        total_revenue = gate_income + lodging_income 
        
        net_profit_budget = total_revenue - (total_budget_expense + feast_budget_expense)
        net_profit_actual = total_revenue - (total_actual_expense + feast_budget_expense) 
        
        kingdom_share = 0.0
        group_share = 0.0
        
        if self.event_type == "Kingdom" and net_profit_actual > 0:
            kingdom_share = net_profit_actual * 0.5
            group_share = net_profit_actual * 0.5
        else:
            group_share = net_profit_actual

        return {
            "total_budget_expense": total_budget_expense + feast_budget_expense,
            "total_actual_expense": total_actual_expense + feast_budget_expense,
            "total_revenue": total_revenue + feast_budget_expense, 
            "net_profit_budget": net_profit_budget,
            "net_profit_actual": net_profit_actual,
            "kingdom_share": kingdom_share,
            "group_share": group_share,
            "feast_budget": feast_budget_expense
        }

# ==========================================
# PDF GENERATION
# ==========================================
def create_pdf(bid: EventBid, financials: dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    elements.append(Paragraph("Kingdom of Meridies Event Bid", styles['Heading1']))
    elements.append(Spacer(1, 12))
    
    # Event Info
    elements.append(Paragraph(f"<b>Event:</b> {bid.event_name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Group:</b> {bid.group_name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {bid.start_date} to {bid.end_date}", styles['Normal']))
    elements.append(Paragraph(f"<b>Type:</b> {bid.event_type} ({bid.kingdom_event_type if bid.event_type=='Kingdom' else ''})", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Stewards & Staff
    elements.append(Paragraph("<b>Event Staff:</b>", styles['Heading3']))
    
    if bid.group_seneschal_name:
        elements.append(Paragraph(f"Seneschal: {bid.group_seneschal_name} - {bid.group_seneschal_contact}", styles['Normal']))
    if bid.reservationist_name:
        elements.append(Paragraph(f"Reservationist: {bid.reservationist_name} - {bid.reservationist_contact}", styles['Normal']))
    
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Event Stewards:</b>", styles['Heading4']))
    for s in bid.event_stewards:
        if s['name']: elements.append(Paragraph(f"{s['name']} - {s['contact']}", styles['Normal']))
        
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Feast Stewards:</b>", styles['Heading4']))
    for s in bid.feast_stewards:
        if s['name']: elements.append(Paragraph(f"{s['name']} - {s['contact']}", styles['Normal']))
        
    elements.append(Spacer(1, 12))
    
    # Site Info
    elements.append(Paragraph(f"<b>Site:</b> {bid.site_name}", styles['Heading3']))
    elements.append(Paragraph(f"Address: {bid.site_address}", styles['Normal']))
    elements.append(Paragraph(f"Contact: {bid.site_contact_name} ({bid.site_contact_info})", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Amenities Summary
    elements.append(Paragraph("<b>Amenities Snapshot</b>", styles['Heading3']))
    amenities = []
    if bid.ada_ramps: amenities.append(f"ADA Ramps ({bid.ada_ramps_count})")
    if bid.ada_bathrooms: amenities.append(f"ADA Bathrooms ({bid.ada_bathrooms_count})")
    if bid.alcohol_policy != "Dry": amenities.append(f"Alcohol: {bid.alcohol_policy}")
    if bid.kitchen_access: amenities.append("Kitchen Access")
    if bid.cabins_available: amenities.append(f"Cabins ({bid.cabins_total_beds} beds)")
    
    elements.append(Paragraph(", ".join(amenities), styles['Normal']))
    
    if bid.ada_comment:
        elements.append(Paragraph(f"<i>ADA Notes: {bid.ada_comment}</i>", styles['Normal']))
        
    elements.append(Spacer(1, 12))
    
    if bid.kitchen_access:
        elements.append(Paragraph(f"<b>Kitchen:</b> {bid.kitchen_burners} Burners, {bid.kitchen_ovens} Ovens, {bid.kitchen_sinks} Sinks", styles['Normal']))
        elements.append(Spacer(1, 12))

    # Financials
    elements.append(Paragraph("<b>Financial Summary</b>", styles['Heading3']))
    data = [
        ["Item", "Budgeted", "Actual"],
        ["Total Revenue", f"${financials['total_revenue']:.2f}", "-"],
        ["Total Expenses", f"${financials['total_budget_expense']:.2f}", f"${financials['total_actual_expense']:.2f}"],
        ["NET PROFIT", f"${financials['net_profit_budget']:.2f}", f"${financials['net_profit_actual']:.2f}"]
    ]
    
    t = Table(data, colWidths=[200, 100, 100])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# STREAMLIT GUI
# ==========================================
def main():
    st.set_page_config(page_title="Meridies Bidder", layout="wide", page_icon=KINGDOM_LOGO_URL)
    
    # Init State
    if "bid" not in st.session_state: st.session_state.bid = EventBid()
    if "is_admin" not in st.session_state: st.session_state.is_admin = False
    bid = st.session_state.bid

    # --- SIDEBAR ---
    with st.sidebar:
        # DB Status Indicator
        conn_check = get_db_connection()
        if conn_check:
            st.success("🟢 Database Online")
            conn_check.close()
        else:
            st.error("🔴 Database Offline")
            
        st.divider()

        # Admin Login
        if not st.session_state.is_admin:
            with st.expander("🔐 Admin Access"):
                pwd = st.text_input("Password", type="password")
                if st.button("Login"):
                    # Check secrets, fallback for testing
                    real_pass = st.secrets["general"]["admin_password"] if "general" in st.secrets else "Meridies2024"
                    if pwd == real_pass:
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("Wrong Password")
        else:
            if st.button("Log Out"):
                st.session_state.is_admin = False
                st.rerun()
            st.success("Admin Mode Active")
        
        st.divider()
        
        # Load Site
        active_sites = load_sites_from_db(include_archived=st.session_state.is_admin)
        options = ["Select a Site..."] + list(active_sites.keys())
        choice = st.selectbox("Load Known Site", options)
        if choice != "Select a Site..." and st.button("Load Data"):
            bid.apply_site_profile(active_sites[choice])
            st.success(f"Loaded {choice}")
            st.rerun()
            
        st.divider()
        
        # Load JSON
        uploaded = st.file_uploader("Load Saved Bid (.json)", type="json")
        if uploaded:
            bid.load_data(json.load(uploaded))
            st.success("Bid Loaded")

    # --- HEADER ---
    col1, col2 = st.columns([1, 6])
    with col1: st.image(KINGDOM_LOGO_URL, width=80)
    with col2: 
        st.title("Kingdom of Meridies Event Bid Tool")
        st.caption("Budgeting, Site Database, and Reporting System")

    # --- TABS FOR LAYOUT ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "1. Event Info", "2. Site Info", "3. Amenities & Kitchen", "4. Income", "5. Expenses", "6. Report"
    ])

    # --- TAB 1: EVENT INFO ---
    with tab1:
        st.subheader("Event Basics")
        c1, c2, c3 = st.columns(3)
        bid.group_name = c1.text_input("Group Name", bid.group_name)
        bid.event_name = c2.text_input("Event Name", bid.event_name)
        
        # Type Selection
        bid.event_type = c3.selectbox("Event Type", ["Local", "Kingdom"], index=0 if bid.event_type=="Local" else 1)
        if bid.event_type == "Kingdom":
            k_opts = [
                "Fighters Collegium/War College",
                "Meridian Challenge of Arms",
                "Spring Coronation",
                "Spring Crown List/Kingdom A&S",
                "Royal University of Meridies",
                "Meridian Grand Tournament",
                "Fall Coronation",
                "Fall Crown List"
            ]
            try: idx = k_opts.index(bid.kingdom_event_type) if bid.kingdom_event_type in k_opts else 0
            except: idx = 0
            bid.kingdom_event_type = st.selectbox("Kingdom Event", k_opts, index=idx)
        
        d1, d2, d3 = st.columns(3)
        bid.start_date = d1.date_input("Start Date", bid.start_date)
        bid.end_date = d2.date_input("End Date", bid.end_date)
        bid.is_single_day = d3.checkbox("Single Day Event?", bid.is_single_day)
        
        st.markdown("---")
        st.subheader("Event Staff")
        st.caption("Note: Contact info is included in the PDF report but NOT saved to the public database.")
        
        # Group Officers
        go1, go2 = st.columns(2)
        with go1:
            st.markdown("**Group Seneschal**")
            bid.group_seneschal_name = st.text_input("Seneschal Name", bid.group_seneschal_name)
            bid.group_seneschal_contact = st.text_input("Phone/Email", bid.group_seneschal_contact, key="gs_contact")
        with go2:
            st.markdown("**Reservationist**")
            bid.reservationist_name = st.text_input("Reservationist Name", bid.reservationist_name)
            bid.reservationist_contact = st.text_input("Phone/Email", bid.reservationist_contact, key="res_contact")

        st.markdown("---")
        
        # Stewards
        c_evt, c_fst = st.columns(2)
        with c_evt:
            st.markdown("**Event Stewards**")
            for i, steward in enumerate(bid.event_stewards):
                c_name, c_contact = st.columns(2)
                steward['name'] = c_name.text_input(f"Steward {i+1} Name", steward['name'])
                steward['contact'] = c_contact.text_input(f"Phone/Email", steward['contact'], key=f"ec{i}")
                
        with c_fst:
            st.markdown("**Feast Stewards**")
            for i, steward in enumerate(bid.feast_stewards):
                c_name, c_contact = st.columns(2)
                steward['name'] = c_name.text_input(f"Feastcrat {i+1} Name", steward['name'])
                steward['contact'] = c_contact.text_input(f"Phone/Email", steward['contact'], key=f"fc{i}")

    # --- TAB 2: SITE INFO ---
    with tab2:
        st.subheader("Site Contact & Basics")
        c1, c2 = st.columns(2)
        bid.site_name = c1.text_input("Site Name", bid.site_name)
        bid.site_address = c2.text_input("Site Address", bid.site_address)
        
        c3, c4, c5 = st.columns(3)
        bid.site_contact_name = c3.text_input("Site Contact Person", bid.site_contact_name)
        bid.site_contact_info = c4.text_input("Site Phone/Email", bid.site_contact_info)
        bid.max_capacity = c5.number_input("Max Site Capacity", value=bid.max_capacity, step=10)

    # --- TAB 3: AMENITIES ---
    with tab3:
        st.subheader("ADA Access")
        a1, a2, a3, a4 = st.columns(4)
        if a1.checkbox("Ramps?", bid.ada_ramps):
            bid.ada_ramps = True
            bid.ada_ramps_count = a1.number_input("Qty Ramps", bid.ada_ramps_count)
        else: bid.ada_ramps = False
            
        if a2.checkbox("ADA Showers?", bid.ada_showers):
            bid.ada_showers = True
            bid.ada_showers_count = a2.number_input("Qty Showers", bid.ada_showers_count)
        else: bid.ada_showers = False
            
        if a3.checkbox("ADA Bathrooms?", bid.ada_bathrooms):
            bid.ada_bathrooms = True
            bid.ada_bathrooms_count = a3.number_input("Qty Bathrooms", bid.ada_bathrooms_count)
        else: bid.ada_bathrooms = False
            
        if a4.checkbox("ADA Parking?", bid.ada_parking):
            bid.ada_parking = True
            bid.ada_parking_count = a4.number_input("Qty Spaces", bid.ada_parking_count)
        else: bid.ada_parking = False
            
        bid.ada_comment = st.text_area("ADA Access Not Listed / Notes", bid.ada_comment, height=60)
        
        st.markdown("---")
        st.subheader("General Facilities")
        g1, g2, g3 = st.columns(3)
        bid.showers_count = g1.number_input("Total Showers", bid.showers_count)
        bid.bathrooms_count = g2.number_input("Total Bathrooms", bid.bathrooms_count)
        
        alco_opts = ["Dry (No)", "Wet (Yes)", "Discreetly Wet (No original containers)"]
        try: idx = alco_opts.index(f"{bid.alcohol_policy}")
        except: idx = 0
        bid.alcohol_policy = g3.selectbox("Alcohol Policy", alco_opts, index=0)
        if bid.alcohol_policy != "Dry (No)":
            st.warning("⚠️ Reminder: Ensure you have Alcohol Insurance if required.")

        st.markdown("---")
        c_camp, c_cabin = st.columns(2)
        with c_camp:
            st.markdown("**Camping**")
            bid.camping_modern = st.checkbox("Modern Tents Allowed", bid.camping_modern)
            bid.camping_period = st.checkbox("Period Tents Allowed", bid.camping_period)
            if st.checkbox("Ground Fires Permitted?", bid.ground_fires):
                bid.ground_fires = True
                bid.ground_fires_restrictions = st.text_input("Fire Restrictions", bid.ground_fires_restrictions)
            else: bid.ground_fires = False
            
        with c_cabin:
            st.markdown("**Cabins**")
            if st.checkbox("Cabins Available?", bid.cabins_available):
                bid.cabins_available = True
                cc1, cc2 = st.columns(2)
                bid.cabins_total_beds = cc1.number_input("Total Beds", bid.cabins_total_beds)
                bid.cabins_per_cabin = cc2.number_input("Beds per Cabin", bid.cabins_per_cabin)
                bid.cabins_top_bunks = cc1.number_input("Qty Top Bunks", bid.cabins_top_bunks)
                bid.cabins_bot_bunks = cc2.number_input("Qty Bottom Bunks", bid.cabins_bot_bunks)
            else: bid.cabins_available = False

        st.markdown("---")
        st.subheader("Kitchen")
        if st.checkbox("Kitchen Access?", bid.kitchen_access):
            bid.kitchen_access = True
            k1, k2, k3, k4 = st.columns(4)
            bid.kitchen_sq_ft = k1.number_input("Sq Footage", bid.kitchen_sq_ft)
            bid.kitchen_burners = k2.number_input("Burners/Eyes", bid.kitchen_burners)
            bid.kitchen_ovens = k3.number_input("Ovens", bid.kitchen_ovens)
            bid.kitchen_sinks = k4.number_input("Sinks", bid.kitchen_sinks)
            
            k_row2_1, k_row2_2 = st.columns(2)
            bid.kitchen_prep_tables = k_row2_1.number_input("Prep Tables", bid.kitchen_prep_tables)
            
            k5, k6, k7, k8 = st.columns(4)
            bid.kitchen_hobart = k5.checkbox("Hobart Dishwasher", bid.kitchen_hobart)
            bid.kitchen_warming_table = k6.checkbox("Warming Table", bid.kitchen_warming_table)
            bid.kitchen_walkin_fridge = k7.checkbox("Walk-In Fridge", bid.kitchen_walkin_fridge)
            bid.kitchen_walkin_freezer = k8.checkbox("Walk-In Freezer", bid.kitchen_walkin_freezer)
            
            k9, k10, k11 = st.columns(3)
            bid.kitchen_household_fridge_count = k9.number_input("Household Fridges", bid.kitchen_household_fridge_count)
            bid.kitchen_household_freezer_count = k10.number_input("Household Freezers", bid.kitchen_household_freezer_count)
            bid.kitchen_ice_maker = k11.checkbox("Ice Maker", bid.kitchen_ice_maker)
        else: bid.kitchen_access = False

        # Classrooms (Dynamic)
        st.markdown("---")
        st.markdown("**Classrooms**")
        def add_classroom():
            bid.classrooms.append({"capacity": 0, "av": False})
        if st.button("Add Classroom"):
            add_classroom()
        if bid.classrooms:
            for idx, room in enumerate(bid.classrooms):
                rc1, rc2, rc3 = st.columns([2, 1, 1])
                room["capacity"] = rc1.number_input(f"Room {idx+1} Capacity", value=int(room["capacity"]), key=f"rcap{idx}")
                room["av"] = rc2.checkbox(f"A/V Available?", value=room["av"], key=f"rav{idx}")
                if rc3.button("Remove", key=f"rrem{idx}"):
                    bid.classrooms.pop(idx)
                    st.rerun()

    # --- TAB 4: INCOME ---
    with tab4:
        st.info("NMS ($10) is automatically added to Non-Member prices below.")
        c1, c2 = st.columns(2)
        bid.daytrip_cost = c1.number_input("Daytrip Member Cost", bid.daytrip_cost)
        c1.metric("Daytrip Non-Member", f"${bid.daytrip_cost + bid.nms_surcharge:.2f}")
        bid.weekend_cost = c2.number_input("Weekend Member Cost", bid.weekend_cost)
        c2.metric("Weekend Non-Member", f"${bid.weekend_cost + bid.nms_surcharge:.2f}")
        
        st.markdown("---")
        st.markdown("**Feast (Siloed Income)**")
        f1, f2, f3 = st.columns(3)
        bid.feast_cost_per_person = f1.number_input("Feast Cost Per Person", bid.feast_cost_per_person)
        bid.feast_seats = f2.number_input("Feast Seats Available", bid.feast_seats)
        feast_budget = bid.feast_cost_per_person * bid.feast_seats
        f3.metric("Total Feast Budget", f"${feast_budget:.2f}")
        
        st.markdown("---")
        st.markdown("**Cabin Income**")
        b1, b2, b3, b4 = st.columns(4)
        b1.info(f"Top Bunks Limit: {bid.cabins_top_bunks}")
        bid.top_bunk_cost = b2.number_input("Cost per Top Bunk", bid.top_bunk_cost)
        b3.info(f"Bottom Bunk Limit: {bid.cabins_bot_bunks}")
        bid.bot_bunk_cost = b4.number_input("Cost per Bottom Bunk", bid.bot_bunk_cost)

    # --- TAB 5: EXPENSES ---
    with tab5:
        st.markdown("### Site Expenses")
        s1, s2, s3 = st.columns(3)
        bid.site_deposit = s1.number_input("Site Deposit", bid.site_deposit)
        bid.site_deposit_refundable = s2.checkbox("Refundable?", bid.site_deposit_refundable)
        if bid.site_deposit_refundable:
            bid.site_deposit_deadline = s3.text_input("Refund Deadline", bid.site_deposit_deadline)
        bid.site_cost = st.number_input("Site Cost (Minus Deposit)", bid.site_cost)
        
        st.markdown("### Operational Budget")
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.markdown("**Item**")
        h2.markdown("**Budgeted**")
        h3.markdown("**Actual (Post-Event)**")
        
        def expense_row(label, budget_attr, actual_attr):
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(label)
            val_b = c2.number_input(f"Budget", value=float(getattr(bid, budget_attr)), key=f"b_{budget_attr}", label_visibility="collapsed")
            val_a = c3.number_input(f"Actual", value=float(getattr(bid, actual_attr)), key=f"a_{actual_attr}", label_visibility="collapsed")
            setattr(bid, budget_attr, val_b)
            setattr(bid, actual_attr, val_a)

        expense_row("Tokens", "budget_tokens", "actual_tokens")
        expense_row("Decorations", "budget_decor", "actual_decor")
        expense_row("Booklet Printing", "budget_booklet", "actual_booklet")
        expense_row("Prizes", "budget_prizes", "actual_prizes")
        
        st.markdown("### Additional Line Items")
        df_expenses = pd.DataFrame(bid.additional_expenses)
        if df_expenses.empty:
            df_expenses = pd.DataFrame(columns=["Item", "Budget", "Actual"])
        edited_df = st.data_editor(df_expenses, num_rows="dynamic", use_container_width=True)
        bid.additional_expenses = edited_df.to_dict('records')

    # --- TAB 6: REPORT ---
    with tab6:
        st.subheader("Financial Projection & Report")
        c1, c2, c3, c4 = st.columns(4)
        bid.proj_attendees = c1.number_input("Proj. Attendees", bid.proj_attendees)
        bid.proj_feast_sold = c2.number_input("Proj. Feast Sold", bid.proj_feast_sold)
        bid.proj_top_sold = c3.number_input("Proj. Top Bunks", bid.proj_top_sold)
        bid.proj_bot_sold = c4.number_input("Proj. Bottom Bunks", bid.proj_bot_sold)
        
        fin = bid.calculate_financials()
        
        r1, r2 = st.columns(2)
        r1.metric("Total Revenue", f"${fin['total_revenue']:.2f}")
        if fin['total_actual_expense'] > bid.site_cost:
            r2.metric("Actual Profit (Post-Event)", f"${fin['net_profit_actual']:.2f}", 
                       delta=f"{fin['net_profit_actual'] - fin['net_profit_budget']:.2f} vs Budget")
        else:
            r2.metric("Projected Profit (Budget)", f"${fin['net_profit_budget']:.2f}")

        if bid.event_type == "Kingdom":
            st.markdown("#### Kingdom Split (50/50)")
            k1, k2 = st.columns(2)
            k1.metric("Group Share", f"${fin['group_share']:.2f}")
            k2.metric("Kingdom Share", f"${fin['kingdom_share']:.2f}")

    # --- EXPORTS & SAVE ---
    st.markdown("---")
    st.subheader("💾 Actions")
    ex1, ex2, ex3 = st.columns(3)
    pdf_bytes = create_pdf(bid, fin)
    ex1.download_button("Download PDF Report", pdf_bytes, "bid_report.pdf", "application/pdf")
    json_str = json.dumps(bid.to_dict(), indent=4)
    ex2.download_button("Save Bid File (.json)", json_str, "bid_save.json", "application/json")
    flat = bid.__dict__.copy()
    if "classrooms" in flat: flat["classrooms"] = str(flat["classrooms"]) 
    if "event_stewards" in flat: flat["event_stewards"] = str(flat["event_stewards"])
    if "feast_stewards" in flat: flat["feast_stewards"] = str(flat["feast_stewards"])
    if "additional_expenses" in flat: flat["additional_expenses"] = str(flat["additional_expenses"])
    if "kitchen_amenities" in flat: del flat["kitchen_amenities"]
    if "expenses" in flat: del flat["expenses"]
    df_ex = pd.DataFrame([flat])
    csv = df_ex.to_csv(index=False).encode('utf-8')
    ex3.download_button("Export CSV", csv, "bid_data.csv", "text/csv")

    # --- ADMIN DB ---
    if st.session_state.is_admin:
        st.markdown("---")
        with st.expander("☁️ Admin: Database Save"):
            db_name = st.text_input("Save Site As:", bid.site_name)
            if st.button("Save Site to DB"):
                if save_site_to_db(db_name, bid):
                    st.success("Site Saved!")
                    st.cache_data.clear()
        
        with st.expander("🗑️ Admin: Manage Sites"):
            all_sites = load_sites_from_db(include_archived=True)
            if all_sites:
                m_choice = st.selectbox("Manage Site", list(all_sites.keys()))
                s_data = all_sites[m_choice]
                is_arch = s_data.get("archived", False)
                st.write(f"Status: {'🔴 Archived' if is_arch else '🟢 Active'}")
                b1, b2 = st.columns(2)
                if b1.button("Toggle Archive"):
                    if toggle_archive_status(m_choice, s_data, not is_arch):
                        st.success("Updated")
                        st.cache_data.clear()
                        st.rerun()
                if b2.button("DELETE PERMANENTLY"):
                    if delete_site_permanently(m_choice):
                        st.success("Deleted")
                        st.cache_data.clear()
                        st.rerun()

if __name__ == "__main__":
    main()
