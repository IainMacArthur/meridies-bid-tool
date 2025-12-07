import streamlit as st
import json
import math
import pandas as pd
from datetime import datetime, time
import io

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ==========================================
# CONFIGURATION & ASSETS
# ==========================================
KINGDOM_LOGO_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQMZ0z9WhWg9G_roekRq7BHmd08icwmjOl6Qg&s"

# ==========================================
# INTERNAL SITE DATABASE (NO API REQUIRED)
# ==========================================
# This acts as your "Living Database". You can add as many sites here as you want.
# When a user selects one, it pre-fills the Site Facilities and Costs.
KNOWN_SITES = {
    "Select a Site...": None, # Default empty option
    "Example State Park Group Camp": {
        "site_flat_fee": 1200.00,
        "site_variable_cost": 5.00,
        "camping_allowed": True,
        "fires_allowed": True,
        "alcohol_policy": "Wet (yes)",
        "kitchen_size": "Large",
        "kitchen_sq_ft": 1500,
        "kitchen_burners": 8,
        "kitchen_ovens": 4,
        "kitchen_3bay_sinks": 2,
        "kitchen_prep_tables": 4,
        "kitchen_garbage_cans": 6,
        "kitchen_fridge_household": 1,
        "kitchen_freezer_household": 1,
        "kitchen_amenities": ["Walk-in Fridge", "Ice Machine", "Pots/Pans"],
        "classrooms_small": 2,
        "classrooms_med": 1,
        "classrooms_large": 1,
        "ada_ramps": True,
        "ada_parking": True,
        "ada_parking_count": 4,
        "ada_bathrooms": True,
        "ada_bathroom_count": 2,
        "beds_bot_qty": 40,
        "beds_top_qty": 40
    }
}

# ==========================================
# CORE LOGIC CLASS
# ==========================================
class EventBid:
    def __init__(self):
        # Metadata
        self.kingdom_event_name = "N/A"
        self.start_date = None 
        self.gate_time = None  
        self.is_single_day = False

        # Staffing
        self.event_stewards = ["", "", "", ""] 
        self.feast_stewards = ["", "", ""]      

        # Expenses
        self.expenses = {} 
        self.event_type = "KINGDOM"
        
        # Site Costs
        self.site_flat_fee = 0.0
        self.site_variable_cost = 0.0
        
        # Site Amenities
        self.camping_allowed = False
        self.fires_allowed = False
        self.alcohol_policy = "Dry (no)" 
        self.classrooms_small = 0
        self.classrooms_med = 0
        self.classrooms_large = 0
        self.av_equipment = ""
        
        # ADA
        self.ada_ramps = False
        self.ada_parking = False
        self.ada_parking_count = 0 # NEW
        self.ada_bathrooms = False
        self.ada_bathroom_count = 0 # NEW
        
        # Kitchen
        self.kitchen_size = "None"
        self.kitchen_sq_ft = 0 # NEW
        self.kitchen_burners = 0
        self.kitchen_ovens = 0
        self.kitchen_3bay_sinks = 0 # NEW
        self.kitchen_prep_tables = 0 # NEW
        self.kitchen_garbage_cans = 0 # NEW
        self.kitchen_fridge_household = 0 # NEW
        self.kitchen_freezer_household = 0 # NEW
        self.kitchen_amenities = [] 
        
        # Gate Pricing
        self.ticket_weekend_member = 0.0
        self.ticket_daytrip_member = 0.0
        self.nms_surcharge = 10.0
        
        # Feast (Siloed)
        self.feast_ticket_price = 0.0
        self.food_cost_per_person = 0.0 
        self.feast_capacity = 0
        
        # Lodging (Siloed)
        self.beds_top_qty = 0
        self.beds_top_price = 0.0
        self.beds_bot_qty = 0
        self.beds_bot_price = 0.0

    def to_dict(self):
        return {
            'kingdom_event_name': self.kingdom_event_name,
            'start_date': str(self.start_date) if self.start_date else None,
            'gate_time': str(self.gate_time) if self.gate_time else None,
            'is_single_day': self.is_single_day,
            'event_stewards': self.event_stewards,
            'feast_stewards': self.feast_stewards,
            'site_flat_fee': self.site_flat_fee,
            'site_variable_cost': self.site_variable_cost,
            'camping_allowed': self.camping_allowed,
            'fires_allowed': self.fires_allowed,
            'alcohol_policy': self.alcohol_policy,
            'classrooms_small': self.classrooms_small,
            'classrooms_med': self.classrooms_med,
            'classrooms_large': self.classrooms_large,
            'av_equipment': self.av_equipment,
            'ada_ramps': self.ada_ramps,
            'ada_parking': self.ada_parking,
            'ada_parking_count': self.ada_parking_count,
            'ada_bathrooms': self.ada_bathrooms,
            'ada_bathroom_count': self.ada_bathroom_count,
            'kitchen_size': self.kitchen_size,
            'kitchen_sq_ft': self.kitchen_sq_ft,
            'kitchen_burners': self.kitchen_burners,
            'kitchen_ovens': self.kitchen_ovens,
            'kitchen_3bay_sinks': self.kitchen_3bay_sinks,
            'kitchen_prep_tables': self.kitchen_prep_tables,
            'kitchen_garbage_cans': self.kitchen_garbage_cans,
            'kitchen_fridge_household': self.kitchen_fridge_household,
            'kitchen_freezer_household': self.kitchen_freezer_household,
            'kitchen_amenities': self.kitchen_amenities,
            'ticket_weekend_member': self.ticket_weekend_member,
            'ticket_daytrip_member': self.ticket_daytrip_member,
            'feast_ticket_price': self.feast_ticket_price,
            'food_cost_per_person': self.food_cost_per_person,
            'feast_capacity': self.feast_capacity,
            'beds_top_qty': self.beds_top_qty,
            'beds_top_price': self.beds_top_price,
            'beds_bot_qty': self.beds_bot_qty,
            'beds_bot_price': self.beds_bot_price,
            'expenses': self.expenses
        }

    def load_data(self, data):
        self.kingdom_event_name = data.get('kingdom_event_name', "N/A")
        
        d_str = data.get('start_date')
        if d_str and d_str != 'None':
            try:
                self.start_date = datetime.strptime(d_str, "%Y-%m-%d").date()
            except:
                self.start_date = None
        
        t_str = data.get('gate_time')
        if t_str and t_str != 'None':
            try:
                self.gate_time = datetime.strptime(t_str, "%H:%M:%S").time()
            except:
                self.gate_time = None
                
        self.is_single_day = data.get('is_single_day', False)

        self.event_stewards = data.get('event_stewards', ["", "", "", ""])
        self.feast_stewards = data.get('feast_stewards', ["", "", ""])
        
        self.site_flat_fee = data.get('site_flat_fee', 0.0)
        self.site_variable_cost = data.get('site_variable_cost', 0.0)
        
        self.camping_allowed = data.get('camping_allowed', False)
        self.fires_allowed = data.get('fires_allowed', False)
        self.alcohol_policy = data.get('alcohol_policy', "Dry (no)")

        self.classrooms_small = data.get('classrooms_small', 0)
        self.classrooms_med = data.get('classrooms_med', 0)
        self.classrooms_large = data.get('classrooms_large', 0)
        self.av_equipment = data.get('av_equipment', "")
        
        # ADA
        self.ada_ramps = data.get('ada_ramps', False)
        self.ada_parking = data.get('ada_parking', False)
        self.ada_parking_count = data.get('ada_parking_count', 0)
        self.ada_bathrooms = data.get('ada_bathrooms', False)
        self.ada_bathroom_count = data.get('ada_bathroom_count', 0)
        
        # Kitchen
        self.kitchen_size = data.get('kitchen_size', "None")
        self.kitchen_sq_ft = data.get('kitchen_sq_ft', 0)
        self.kitchen_burners = data.get('kitchen_burners', 0)
        self.kitchen_ovens = data.get('kitchen_ovens', 0)
        self.kitchen_3bay_sinks = data.get('kitchen_3bay_sinks', 0)
        self.kitchen_prep_tables = data.get('kitchen_prep_tables', 0)
        self.kitchen_garbage_cans = data.get('kitchen_garbage_cans', 0)
        self.kitchen_fridge_household = data.get('kitchen_fridge_household', 0)
        self.kitchen_freezer_household = data.get('kitchen_freezer_household', 0)
        self.kitchen_amenities = data.get('kitchen_amenities', [])
        
        self.ticket_weekend_member = data.get('ticket_weekend_member', 0.0)
        self.ticket_daytrip_member = data.get('ticket_daytrip_member', 0.0)
        self.feast_ticket_price = data.get('feast_ticket_price', 0.0)
        self.food_cost_per_person = data.get('food_cost_per_person', 0.0)
        self.feast_capacity = data.get('feast_capacity', 0)
        self.beds_top_qty = data.get('beds_top_qty', 0)
        self.beds_top_price = data.get('beds_top_price', 0.0)
        self.beds_bot_qty = data.get('beds_bot_qty', 0)
        self.beds_bot_price = data.get('beds_bot_price', 0.0)
        self.expenses = data.get('expenses', {})

    def apply_site_profile(self, profile):
        """Helper to load just the site specific data from the database."""
        if not profile: return
        self.site_flat_fee = profile.get("site_flat_fee", 0.0)
        self.site_variable_cost = profile.get("site_variable_cost", 0.0)
        self.camping_allowed = profile.get("camping_allowed", False)
        self.fires_allowed = profile.get("fires_allowed", False)
        self.alcohol_policy = profile.get("alcohol_policy", "Dry (no)")
        self.kitchen_size = profile.get("kitchen_size", "None")
        self.kitchen_sq_ft = profile.get("kitchen_sq_ft", 0)
        self.kitchen_burners = profile.get("kitchen_burners", 0)
        self.kitchen_ovens = profile.get("kitchen_ovens", 0)
        self.kitchen_3bay_sinks = profile.get("kitchen_3bay_sinks", 0)
        self.kitchen_prep_tables = profile.get("kitchen_prep_tables", 0)
        self.kitchen_garbage_cans = profile.get("kitchen_garbage_cans", 0)
        self.kitchen_fridge_household = profile.get("kitchen_fridge_household", 0)
        self.kitchen_freezer_household = profile.get("kitchen_freezer_household", 0)
        self.kitchen_amenities = profile.get("kitchen_amenities", [])
        self.classrooms_small = profile.get("classrooms_small", 0)
        self.classrooms_med = profile.get("classrooms_med", 0)
        self.classrooms_large = profile.get("classrooms_large", 0)
        self.ada_ramps = profile.get("ada_ramps", False)
        self.ada_parking = profile.get("ada_parking", False)
        self.ada_parking_count = profile.get("ada_parking_count", 0)
        self.ada_bathrooms = profile.get("ada_bathrooms", False)
        self.ada_bathroom_count = profile.get("ada_bathroom_count", 0)
        self.beds_bot_qty = profile.get("beds_bot_qty", 0)
        self.beds_top_qty = profile.get("beds_top_qty", 0)

    def get_total_fixed_costs(self, mode='projected'):
        total_ops = sum(item[mode] for item in self.expenses.values())
        return self.site_flat_fee + total_ops

    def calculate_bed_revenue(self, projected_occupancy_pct=1.0):
        top_rev = (self.beds_top_qty * projected_occupancy_pct) * self.beds_top_price
        bot_rev = (self.beds_bot_qty * projected_occupancy_pct) * self.beds_bot_price
        return top_rev + bot_rev

    def calculate_gate_break_even(self):
        # NOTE: Feast and Beds are SILOED. They are not included here.
        # This calculates how many bodies need to pass gate to cover 
        # Site Rental + Operational Expenses.
        margin = self.ticket_weekend_member - self.site_variable_cost
        fixed_total = self.get_total_fixed_costs(mode='projected')
        if margin <= 0: return None 
        return math.ceil(fixed_total / margin)

    def generate_final_report(self, attend_weekend, attend_daytrip, feast_count, bed_sell_pct, mode='projected'):
        fixed_costs = self.get_total_fixed_costs(mode)
        
        rev_weekend = self.ticket_weekend_member * attend_weekend
        rev_daytrip = self.ticket_daytrip_member * attend_daytrip
        total_gate_revenue = rev_weekend + rev_daytrip
        
        total_attendees = attend_weekend + attend_daytrip
        total_variable = self.site_variable_cost * total_attendees
        
        gate_net = total_gate_revenue - fixed_costs - total_variable

        feast_revenue = self.feast_ticket_price * feast_count
        feast_expenses = self.food_cost_per_person * feast_count
        feast_net = feast_revenue - feast_expenses

        bed_revenue = self.calculate_bed_revenue(bed_sell_pct)
        bed_net = bed_revenue 

        total_net = gate_net + feast_net + bed_net
        
        kingdom_share = 0.0
        group_share = 0.0

        if total_net > 0:
            if self.event_type == "KINGDOM":
                kingdom_share = total_net * 0.5
                group_share = total_net * 0.5
            else:
                kingdom_share = 0.0
                group_share = total_net

        return {
            "break_even": self.calculate_gate_break_even(),
            "total_net": total_net,
            "kingdom_share": kingdom_share,
            "group_share": group_share,
            "gate_net": gate_net,
            "feast_net": feast_net,
            "bed_net": bed_net,
            "total_revenue": total_gate_revenue + feast_revenue + bed_revenue,
            "total_expense": fixed_costs + total_variable + feast_expenses
        }

# ==========================================
# PDF GENERATION LOGIC
# ==========================================
def create_pdf(bid):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    h2_style = styles['Heading2']
    h3_style = styles['Heading3']
    normal_style = styles['Normal']
    
    elements = []
    
    # --- HEADER ---
    elements.append(Paragraph("Kingdom of Meridies Event Bid", title_style))
    elements.append(Spacer(1, 12))
    
    # Event Info Table
    date_str = str(bid.start_date) if bid.start_date else "TBD"
    time_str = str(bid.gate_time) if bid.gate_time else "TBD"
    
    data_info = [
        ["Event Name:", bid.kingdom_event_name],
        ["Type:", bid.event_type],
        ["Date:", date_str],
        ["Gate Opens:", time_str],
        ["Duration:", "Single Day" if bid.is_single_day else "Weekend"]
    ]
    t_info = Table(data_info, colWidths=[100, 300])
    t_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 12))

    # --- STAFFING ---
    elements.append(Paragraph("Staffing", h2_style))
    autocrats = ", ".join([s for s in bid.event_stewards if s])
    feastcrats = ", ".join([s for s in bid.feast_stewards if s])
    
    elements.append(Paragraph(f"<b>Event Stewards:</b> {autocrats if autocrats else 'None Listed'}", normal_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Feast Stewards:</b> {feastcrats if feastcrats else 'None Listed'}", normal_style))
    elements.append(Spacer(1, 12))
    
    # --- FACILITIES ---
    elements.append(Paragraph("Site Facilities & Rules", h2_style))
    
    # Facilities List
    fac_data = [
        ["Camping:", "Allowed" if bid.camping_allowed else "No"],
        ["Ground Fires:", "Allowed" if bid.fires_allowed else "No"],
        ["Alcohol:", bid.alcohol_policy],
        ["Classrooms:", f"S:{bid.classrooms_small} / M:{bid.classrooms_med} / L:{bid.classrooms_large}"],
        ["ADA Access:", f"{'Ramps ' if bid.ada_ramps else ''}{'Parking ' if bid.ada_parking else ''}{'Bathrooms ' if bid.ada_bathrooms else ''}"],
        ["ADA Specifics:", f"{bid.ada_parking_count} Spots / {bid.ada_bathroom_count} Bathrooms"]
    ]
    t_fac = Table(fac_data, colWidths=[100, 300])
    t_fac.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')]))
    elements.append(t_fac)
    elements.append(Spacer(1, 12))

    # Kitchen Details
    elements.append(Paragraph("Kitchen Specs", h3_style))
    k_data = [
        ["Size / Sq Ft:", f"{bid.kitchen_size} / {bid.kitchen_sq_ft} sq ft"],
        ["Equipment:", f"{bid.kitchen_burners} Burners, {bid.kitchen_ovens} Ovens"],
        ["Work Space:", f"{bid.kitchen_3bay_sinks} Sinks (3-bay), {bid.kitchen_prep_tables} Prep Tables"],
        ["Storage/Trash:", f"{bid.kitchen_garbage_cans} Garbage Cans"],
        ["Household Cold:", f"{bid.kitchen_fridge_household} Fridges, {bid.kitchen_freezer_household} Freezers"]
    ]
    t_k = Table(k_data, colWidths=[100, 300])
    t_k.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')]))
    elements.append(t_k)
    
    if bid.kitchen_amenities:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Other Amenities:</b> {', '.join(bid.kitchen_amenities)}", normal_style))
        
    elements.append(Spacer(1, 12))
    
    # --- PRICING ---
    elements.append(Paragraph("Proposed Pricing", h2_style))
    price_label = "Weekend Member" if not bid.is_single_day else "Full Day Member"
    
    price_data = [
        ["Ticket Type", "Member Price", "Non-Member Price"],
        [price_label, f"${bid.ticket_weekend_member:.2f}", f"${bid.ticket_weekend_member + bid.nms_surcharge:.2f}"],
        ["Daytrip/Partial", f"${bid.ticket_daytrip_member:.2f}", f"${bid.ticket_daytrip_member + bid.nms_surcharge:.2f}"],
        ["Feast Ticket", f"${bid.feast_ticket_price:.2f}", "-"],
    ]
    t_price = Table(price_data, colWidths=[150, 100, 120])
    t_price.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t_price)
    elements.append(Spacer(1, 12))
    
    # --- BUDGET & FINANCIALS ---
    elements.append(Paragraph("Projected Budget Summary", h2_style))
    
    # Calculate stats for the PDF (assuming standard 100/50 projection for the report snapshot)
    res = bid.generate_final_report(100, 20, 50, 0.5, mode='projected')
    
    fin_data = [
        ["Category", "Amount"],
        ["Site Costs (Fixed)", f"${bid.site_flat_fee:.2f}"],
        ["Site Costs (Variable)", f"${bid.site_variable_cost:.2f} / person"],
        ["Projected Expense Total", f"${res['total_expense']:.2f}"],
        ["Projected Revenue Total", f"${res['total_revenue']:.2f}"],
        ["NET PROFIT", f"${res['total_net']:.2f}"],
        ["BREAK EVEN (Gate Only)", f"{res['break_even']} Attendees"]
    ]
    
    t_fin = Table(fin_data, colWidths=[200, 150])
    t_fin.setStyle(TableStyle([
        ('FONTNAME', (0,-2), (-1,-1), 'Helvetica-Bold'), # Bold last two rows
        ('LINEABOVE', (0,-2), (-1,-2), 1, colors.black),
    ]))
    elements.append(t_fin)
    elements.append(Spacer(1, 12))
    
    if bid.event_type == "KINGDOM":
        split_data = [["Kingdom Share (50%)", f"${res['kingdom_share']:.2f}"], ["Group Share (50%)", f"${res['group_share']:.2f}"]]
        t_split = Table(split_data, colWidths=[200, 150])
        elements.append(t_split)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# STREAMLIT GUI
# ==========================================
def main():
    st.set_page_config(
        page_title="Meridies Bid Calculator", 
        layout="wide",
        page_icon=KINGDOM_LOGO_URL
    )

    # PAGE HEADER
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.image(KINGDOM_LOGO_URL, width=100)
    with col_title:
        st.title("Kingdom of Meridies Event Bidder")
        st.caption("A tool for budgeting and historical site analysis.")
    
    # Initialize Bid Object
    bid = EventBid()
    
    # --- Sidebar (Upload Logic) ---
    with st.sidebar:
        st.header("📂 Data Management")
        
        # 1. Database Load
        st.subheader("1. Load Known Site")
        selected_site = st.selectbox("Choose a Historical Site Profile", options=KNOWN_SITES.keys())
        if selected_site and selected_site != "Select a Site...":
            if st.button("Load Site Data"):
                profile = KNOWN_SITES[selected_site]
                bid.apply_site_profile(profile)
                st.success(f"Loaded details for {selected_site}")

        st.markdown("---")

        # 2. File Upload
        st.subheader("2. Load Saved Bid")
        uploaded_file = st.file_uploader("Upload a Bid File (.json)", type=['json'])

    # Check if a file was just uploaded (Overwrites database selection)
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            bid.load_data(data)
            st.sidebar.success("✅ Bid Loaded Successfully!")
        except Exception as e:
            st.sidebar.error(f"Error loading file: {e}")

    # --- Main Form ---
    
    # 1. Event Type & Name
    st.subheader("1. Event Information")
    col_type, col_name = st.columns([1,2])
    
    with col_type:
        bid.event_type = st.selectbox("Event Type", ["KINGDOM", "LOCAL"], index=0 if bid.event_type == "KINGDOM" else 1)
        
    with col_name:
        if bid.event_type == "KINGDOM":
            kle_options = [
                "Fighters Collegium/War College",
                "Meridian Challenge of Arms",
                "Spring Coronation",
                "Spring Crown/Kingdom A&S",
                "Royal University of Meridies",
                "Meridian Grand Tournament",
                "Fall Coronation",
                "Fall Crown List"
            ]
            try:
                curr_index = kle_options.index(bid.kingdom_event_name)
            except ValueError:
                curr_index = 0
            bid.kingdom_event_name = st.selectbox("Select Kingdom Event", kle_options, index=curr_index)
        else:
            bid.kingdom_event_name = st.text_input("Event Name", value=bid.kingdom_event_name if bid.kingdom_event_name != "N/A" else "Local Event")

    # DATE & TIME SECTION
    dt_col1, dt_col2, dt_col3 = st.columns(3)
    bid.start_date = dt_col1.date_input("Event Start Date", value=bid.start_date, format="MM/DD/YYYY")
    bid.gate_time = dt_col2.time_input("Gate Open Time", value=bid.gate_time)
    bid.is_single_day = dt_col3.checkbox("Is this a Single Day Event?", value=bid.is_single_day, help="Check if the event starts and ends on the same day.")

    if bid.is_single_day:
        st.success("ℹ️ **Single Day Event Mode:** 'Weekend' pricing will represent the 'Full Day' adult price.")

    # STAFFING
    st.markdown("---")
    st.subheader("2. Event Staff")
    staff_c1, staff_c2 = st.columns(2)
    
    with staff_c1:
        st.markdown("**Event Stewards (Autocrats)**")
        for i in range(4):
            bid.event_stewards[i] = st.text_input(f"Event Steward #{i+1}", value=bid.event_stewards[i], key=f"evt_stwd_{i}")
            
    with staff_c2:
        st.markdown("**Feast Stewards**")
        for i in range(3):
            bid.feast_stewards[i] = st.text_input(f"Feast Steward #{i+1}", value=bid.feast_stewards[i], key=f"fst_stwd_{i}")

    # 2. Site Amenities Section
    st.markdown("---")
    st.subheader("3. Site Facilities & Rules")
    
    # ADA ACCESSIBILITY
    with st.expander("Accessibility (ADA)", expanded=True):
        st.caption("Select all that apply to this site:")
        ada_c1, ada_c2, ada_c3, ada_c4 = st.columns(4)
        bid.ada_ramps = ada_c1.checkbox("♿ Ramps / Level Access", value=bid.ada_ramps)
        bid.ada_parking = ada_c2.checkbox("🅿️ ADA Parking Available", value=bid.ada_parking)
        bid.ada_bathrooms = ada_c3.checkbox("🚻 ADA Accessible Bathrooms", value=bid.ada_bathrooms)
        
        st.markdown("**ADA Quantities**")
        ac1, ac2 = st.columns(2)
        bid.ada_parking_count = ac1.number_input("Count of ADA Parking Spaces", value=bid.ada_parking_count, min_value=0)
        bid.ada_bathroom_count = ac2.number_input("Count of ADA Bathrooms", value=bid.ada_bathroom_count, min_value=0)

    with st.expander("Kitchen & Dining Amenities", expanded=False):
        k1, k2, k3, k4 = st.columns(4)
        bid.kitchen_size = k1.selectbox("Kitchen Size", ["None", "Small", "Medium", "Large", "Giant"], index=0)
        bid.kitchen_sq_ft = k2.number_input("Kitchen Sq. Ft.", value=bid.kitchen_sq_ft, step=10)
        bid.kitchen_burners = k3.number_input("Number of Burners", value=bid.kitchen_burners, min_value=0)
        bid.kitchen_ovens = k4.number_input("Number of Ovens", value=bid.kitchen_ovens, min_value=0)
        
        st.markdown("**Kitchen Workspace & Storage**")
        kw1, kw2, kw3 = st.columns(3)
        bid.kitchen_3bay_sinks = kw1.number_input("Qty 3-Bay Sinks", value=bid.kitchen_3bay_sinks, min_value=0)
        bid.kitchen_prep_tables = kw2.number_input("Qty Prep Tables", value=bid.kitchen_prep_tables, min_value=0)
        bid.kitchen_garbage_cans = kw3.number_input("Qty Garbage Cans", value=bid.kitchen_garbage_cans, min_value=0)

        st.markdown("**Household Cold Storage** (In addition to Walk-ins)")
        ref1, ref2, ref3 = st.columns(3)
        bid.kitchen_fridge_household = ref1.number_input("Qty Household Fridges", value=bid.kitchen_fridge_household, min_value=0)
        bid.kitchen_freezer_household = ref2.number_input("Qty Household Freezers", value=bid.kitchen_freezer_household, min_value=0)
        
        st.markdown("**Other Equipment:**")
        available_opts = [
            "Hobart Dishwasher", "Food Warmers", "Buffet Warming Table", 
            "Utensils/Pots/Pans", "Ice Machine", "Walk-in Fridge", "Walk-in Freezer"
        ]
        default_opts = [x for x in bid.kitchen_amenities if x in available_opts]
        bid.kitchen_amenities = st.multiselect("Select all that apply:", available_opts, default=default_opts)

    with st.expander("Site Rules & Spaces", expanded=False):
        r1, r2, r3 = st.columns(3)
        bid.camping_allowed = r1.checkbox("⛺ Camping Allowed?", value=bid.camping_allowed)
        bid.fires_allowed = r2.checkbox("🔥 Ground Fires Allowed?", value=bid.fires_allowed)
        
        alcohol_opts = ["Dry (no)", "Wet (yes)", "Discreetly Wet (Yes, no original containers)"]
        try:
            alc_idx = alcohol_opts.index(bid.alcohol_policy)
        except:
            alc_idx = 0
        bid.alcohol_policy = r3.selectbox("Alcohol Policy", alcohol_opts, index=alc_idx)
        
        st.markdown("**Classrooms:**")
        c1, c2, c3 = st.columns(3)
        bid.classrooms_small = c1.number_input("Qty Small Classrooms", value=bid.classrooms_small, min_value=0)
        bid.classrooms_med = c2.number_input("Qty Medium Classrooms", value=bid.classrooms_med, min_value=0)
        bid.classrooms_large = c3.number_input("Qty Large Classrooms", value=bid.classrooms_large, min_value=0)
        
        bid.av_equipment = st.text_area("A/V Equipment Available", value=bid.av_equipment, placeholder="Projectors, Screens, PA Systems...")

    # 3. Gate Pricing
    st.markdown("---")
    st.subheader("4. Gate Ticket Pricing")
    st.info(f"Note: The Non-Member Surcharge (NMS) is fixed at ${bid.nms_surcharge:.2f}. "
            "This calculator excludes NMS from profit calculations as it is a pass-through fee.")
    
    g1, g2, g3, g4 = st.columns(4)
    price_label = "Full Event (Weekend) Member Price ($)" if not bid.is_single_day else "Full Day Member Price ($)"
    
    bid.ticket_weekend_member = g1.number_input(price_label, value=bid.ticket_weekend_member, min_value=0.0)
    bid.ticket_daytrip_member = g2.number_input("Daytrip/Partial Member Price ($)", value=bid.ticket_daytrip_member, min_value=0.0)
    
    g3.metric("Non-Member Full Price", f"${bid.ticket_weekend_member + bid.nms_surcharge:.2f}")
    g4.metric("Non-Member Partial Price", f"${bid.ticket_daytrip_member + bid.nms_surcharge:.2f}")

    # 4. Site Costs
    st.markdown("---")
    st.subheader("5. Site Financials")
    sc1, sc2 = st.columns(2)
    bid.site_flat_fee = sc1.number_input("Site Flat Rental Fee ($)", value=bid.site_flat_fee, min_value=0.0)
    bid.site_variable_cost = sc2.number_input(
        "Variable Cost Per Person Per Day ($)", 
        value=bid.site_variable_cost,
        min_value=0.0,
        help="Leave as 0.00 unless the site charges a specific 'Head Tax' or per-person daily fee."
    )

    # 5. Lodging / Cabins
    st.markdown("---")
    st.subheader("6. Cabins & Lodging")
    st.info("ℹ️ Bed Revenue is siloed. It is added to Net Profit but excluded from Gate Break-Even calculations.")
    with st.expander("Configure Bunks", expanded=False):
        b1, b2, b3, b4 = st.columns(4)
        bid.beds_bot_qty = b1.number_input("Qty: Bottom Bunks", value=bid.beds_bot_qty, step=1, min_value=0)
        bid.beds_bot_price = b2.number_input("Price: Bottom Bunk ($)", value=bid.beds_bot_price, min_value=0.0)
        bid.beds_top_qty = b3.number_input("Qty: Top Bunks", value=bid.beds_top_qty, step=1, min_value=0)
        bid.beds_top_price = b4.number_input("Price: Top Bunk ($)", value=bid.beds_top_price, min_value=0.0)

    # 6. Operational Budget
    st.markdown("---")
    st.subheader("7. Operational Budget (Line Items)")
    st.caption("Categorize expenses to track spending (e.g., Prizes, Decor, Site, Admin).")
    
    current_items = []
    for k, v in bid.expenses.items():
        cat = v.get('category', 'General')
        current_items.append({
            "Category": cat,
            "Item": k, 
            "Projected": v['projected'], 
            "Actual": v['actual']
        })
    
    if not current_items:
        current_items = [{"Category": "Prizes", "Item": "Tournament Token", "Projected": 100.0, "Actual": 0.0}]

    df = pd.DataFrame(current_items)
    
    column_config = {
        "Category": st.column_config.SelectboxColumn(
            "Category",
            options=["Site", "Food", "Decor", "Prizes", "Admin", "Equipment", "Other"],
            required=True
        ),
        "Item": st.column_config.TextColumn("Item Name", required=True),
        "Projected": st.column_config.NumberColumn("Projected ($)", min_value=0.0, format="$%.2f"),
        "Actual": st.column_config.NumberColumn("Actual ($)", min_value=0.0, format="$%.2f")
    }
    
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config=column_config
    )

    bid.expenses = {}
    for index, row in edited_df.iterrows():
        if row["Item"]:
            proj = float(row["Projected"])
            act = float(row["Actual"])
            if proj < 0 or act < 0:
                st.error(f"⚠️ Error in Line Item '{row['Item']}': Costs cannot be negative.")
                st.stop()
            
            bid.expenses[row["Item"]] = {
                'projected': proj, 
                'actual': act,
                'category': row["Category"]
            }

    # 7. Feast
    st.markdown("---")
    st.subheader("8. Feast Details")
    st.info("ℹ️ Feast Costs are siloed. Feast Expense is subtracted from Feast Revenue to create Feast Net. This does not impact Gate Break-Even.")
    f1, f2, f3 = st.columns(3)
    bid.feast_ticket_price = f1.number_input("Feast Ticket Price (Revenue) ($)", value=bid.feast_ticket_price, min_value=0.0)
    bid.food_cost_per_person = f2.number_input("Food Cost Budget (Expense) ($)", value=bid.food_cost_per_person, min_value=0.0)
    bid.feast_capacity = f3.number_input("Feast Hall Capacity", value=int(bid.feast_capacity), step=1, min_value=0)

    # 8. Projections
    st.markdown("---")
    st.subheader("📊 Financial Projections")
    
    c1, c2, c3, c4 = st.columns(4)
    p_label_full = "Projected Full Event Attendees" if not bid.is_single_day else "Projected Full Day Attendees"
    
    proj_weekend = c1.number_input(p_label_full, value=100, step=10, min_value=0)
    proj_daytrip = c2.number_input("Projected Partial/Daytrip Attendees", value=20, step=5, min_value=0)
    proj_feast = c3.number_input("Projected Feast Attendees", value=50, step=10, min_value=0)
    proj_beds = c4.slider("Projected Bed Sales %", 0.0, 1.0, 0.5, format="%d%%")
    
    calc_mode = st.radio("Calculation Mode", ["Projected Budget", "Post-Event Actuals"], horizontal=True)
    mode_key = 'projected' if calc_mode == "Projected Budget" else 'actual'

    if st.button("Calculate Results", type="primary"):
        # --- VALIDATION BLOCK ---
        errors = []
        if proj_feast > bid.feast_capacity:
            errors.append(f"⚠️ Feast Error: You projected {proj_feast} attendees but the hall only holds {bid.feast_capacity}.")
        
        if (bid.ticket_weekend_member <= bid.site_variable_cost) and bid.ticket_weekend_member > 0:
            errors.append("⚠️ Pricing Error: Your Ticket Price is lower than the Variable Cost per person. You will lose money on every attendee.")
            
        if errors:
            for e in errors:
                st.error(e)
        else:
            res = bid.generate_final_report(proj_weekend, proj_daytrip, proj_feast, proj_beds, mode=mode_key)
            
            st.markdown(f"### Net Profit: :green[${res['total_net']:.2f}]")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Break Even (Gate Only)", res['break_even'] if res['break_even'] else "Impossible")
            m2.metric("Kingdom Share (50%)", f"${res['kingdom_share']:.2f}")
            m3.metric("Group Share", f"${res['group_share']:.2f}")
            m4.metric("Total Expenses", f"${res['total_expense']:.2f}")

            with st.expander("See Financial Breakdown"):
                col_fin1, col_fin2 = st.columns(2)
                with col_fin1:
                    st.write("#### Net Calculations (Profit)")
                    st.write(f"**Gate Net:** ${res['gate_net']:.2f}")
                    st.write(f"**Feast Net:** ${res['feast_net']:.2f}")
                    st.write(f"**Bed/Cabin Net:** ${res['bed_net']:.2f}")
                with col_fin2:
                    st.write("#### Totals")
                    st.write(f"**Total Revenue:** ${res['total_revenue']:.2f}")
                    st.write(f"**Total Expenses:** ${res['total_expense']:.2f}")
                
                if mode_key == 'actual':
                    st.info("Results based on ACTUALS column.")

    # --- SAVE TO FILE (JSON & PDF) ---
    st.markdown("---")
    st.subheader("💾 Save & Submit")
    st.caption("Use the JSON file to save your work. Use the PDF file to submit your bid.")
    
    col_save, col_pdf = st.columns(2)
    
    clean_name = bid.kingdom_event_name.replace(" ", "_").replace("/", "-")
    date_str = str(bid.start_date) if bid.start_date else "NoDate"
    
    # JSON DOWNLOAD
    with col_save:
        bid_json = json.dumps(bid.to_dict(), indent=4)
        st.download_button(
            label="1. Download Save File (.json)",
            data=bid_json,
            file_name=f"Bid_SAVE_{clean_name}_{date_str}.json",
            mime="application/json"
        )
        
    # PDF DOWNLOAD
    with col_pdf:
        # Generate PDF Bytes
        pdf_bytes = create_pdf(bid)
        st.download_button(
            label="2. Download Printable Bid (.pdf)",
            data=pdf_bytes,
            file_name=f"Bid_SUBMIT_{clean_name}_{date_str}.pdf",
            mime="application/pdf"
        )
        
    # --- ADMIN: EXPORT SITE TO DB ---
    with st.expander("👑 Admin: Export Site for Database"):
        st.write("Use this to generate the code needed to add this site to the 'KNOWN_SITES' list in the Python script.")
        
        # Create a dictionary of only site attributes
        site_export = {
            "site_flat_fee": bid.site_flat_fee,
            "site_variable_cost": bid.site_variable_cost,
            "camping_allowed": bid.camping_allowed,
            "fires_allowed": bid.fires_allowed,
            "alcohol_policy": bid.alcohol_policy,
            "kitchen_size": bid.kitchen_size,
            "kitchen_sq_ft": bid.kitchen_sq_ft,
            "kitchen_burners": bid.kitchen_burners,
            "kitchen_ovens": bid.kitchen_ovens,
            "kitchen_3bay_sinks": bid.kitchen_3bay_sinks,
            "kitchen_prep_tables": bid.kitchen_prep_tables,
            "kitchen_garbage_cans": bid.kitchen_garbage_cans,
            "kitchen_fridge_household": bid.kitchen_fridge_household,
            "kitchen_freezer_household": bid.kitchen_freezer_household,
            "kitchen_amenities": bid.kitchen_amenities,
            "classrooms_small": bid.classrooms_small,
            "classrooms_med": bid.classrooms_med,
            "classrooms_large": bid.classrooms_large,
            "ada_ramps": bid.ada_ramps,
            "ada_parking": bid.ada_parking,
            "ada_parking_count": bid.ada_parking_count,
            "ada_bathrooms": bid.ada_bathrooms,
            "ada_bathroom_count": bid.ada_bathroom_count,
            "beds_bot_qty": bid.beds_bot_qty,
            "beds_top_qty": bid.beds_top_qty
        }
        
        # Format as Python dictionary string
        site_name_key = st.text_input("Site Name (for Database Key)", value="New Site Name")
        json_str = json.dumps(site_export, indent=4)
        
        st.code(f'"{site_name_key}": {json_str},', language='python')
        st.info("Copy the code above and paste it into the 'KNOWN_SITES' dictionary at the top of the script.")

if __name__ == "__main__":
    main()
