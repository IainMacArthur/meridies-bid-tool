import streamlit as st
from datetime import datetime, date, time
from dataclasses import dataclass, field
from typing import List, Dict
import json
import math
import io

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
# SITE DATABASE (The "Living Database")
# ==========================================
SITE_DATABASE = {
    "Select a Site...": None,
    "Example State Park": {
        "site_name": "Example State Park",
        "site_address": "123 Forest Lane",
        "parking_spaces": 100,
        "bathrooms_count": 4,
        "camping_allowed": True,
        "camping_tents": 50,
        "camping_rv": 10,
        "kitchen_size": "Large",
        "kitchen_sq_ft": 1200,
        "kitchen_stove_burners": 8,
        "kitchen_ovens": 4,
        "kitchen_3bay_sinks": 2,
        "kitchen_prep_tables": 4,
        "kitchen_garbage_cans": 6,
        "kitchen_fridge_household": 1,
        "kitchen_freezer_household": 1,
        "ada_ramps": True,
        "ada_parking": True,
        "ada_parking_count": 4,
        "ada_bathrooms": True,
        "ada_bathroom_count": 2,
        "site_fee": 1200.0,
        "beds_top_qty": 20,
        "beds_top_price": 5.0,
        "beds_bot_qty": 20,
        "beds_bot_price": 10.0
    }
}

# ==========================================
# DATA MODEL
# ==========================================
@dataclass
class EventBid:
    # Basic Event Info
    origin_kingdom: str = "Meridies"
    group_name: str = ""
    event_type: str = "Local"  
    event_name: str = ""
    bid_for_year: int = datetime.now().year
    
    # Site Info
    site_name: str = ""
    site_address: str = ""
    start_date: date = date.today()
    start_time: time = time(17, 0)
    end_date: date = date.today()
    end_time: time = time(12, 0)
    gate_time: time = time(17, 0)
    is_single_day: bool = False
    
    # Staff
    event_stewards: List[str] = field(default_factory=lambda: ["", "", "", ""])
    feast_stewards: List[str] = field(default_factory=lambda: ["", "", ""])
    
    # Site Features
    parking_spaces: int = 0
    bathrooms_count: int = 0
    ada_ramps: bool = False
    ada_parking: bool = False
    ada_parking_count: int = 0
    ada_bathrooms: bool = False
    ada_bathroom_count: int = 0

    # Kitchen
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

    # Camping / Lodging
    camping_allowed: bool = False
    camping_tents: int = 0
    camping_rv: int = 0
    
    # Pricing & Costs
    site_fee: float = 0.0 # Fixed Cost
    site_variable_cost: float = 0.0 # Per Person Cost
    
    ticket_weekend_member: float = 0.0
    ticket_daytrip_member: float = 0.0
    nms_surcharge: float = 10.0  # Default $10 NMS (pass-through)
    
    feast_fee: float = 0.0
    feast_cost_per_person: float = 0.0
    feast_capacity: int = 0
    
    # BEDS (Split Top/Bottom)
    beds_top_qty: int = 0
    beds_top_price: float = 0.0
    beds_bot_qty: int = 0
    beds_bot_price: float = 0.0

    # Expenses
    expenses: Dict[str, Dict] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Data Handling
    # ------------------------------------------------------------------
    def to_dict(self):
        return json.loads(json.dumps(self, default=lambda o: o.isoformat() if isinstance(o, (date, time)) else o.__dict__))

    def load_data(self, data_dict: dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                try:
                    if key in ["start_date", "end_date"] and isinstance(value, str):
                        setattr(self, key, date.fromisoformat(value))
                    elif key in ["start_time", "end_time", "gate_time"] and isinstance(value, str):
                        setattr(self, key, time.fromisoformat(value))
                    else:
                        setattr(self, key, value)
                except Exception as e:
                    st.warning(f"Could not load field '{key}': {e}")

    def apply_site_profile(self, profile):
        if not profile: return
        for key, value in profile.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # ------------------------------------------------------------------
    # Financials (Siloed Logic)
    # ------------------------------------------------------------------
    def get_total_fixed_costs(self, mode="projected"):
        ops_total = sum(item.get(mode, 0) for item in self.expenses.values())
        return self.site_fee + ops_total

    def calculate_projection(self, attend_weekend, attend_daytrip, feast_count, sold_top, sold_bot, mode="projected"):
        fixed_costs = self.get_total_fixed_costs(mode)
        
        # 1. Gate Revenue
        rev_weekend = self.ticket_weekend_member * attend_weekend
        rev_daytrip = self.ticket_daytrip_member * attend_daytrip
        total_gate_revenue = rev_weekend + rev_daytrip
        
        # 2. Variable Site Costs
        total_attendees = attend_weekend + attend_daytrip
        total_variable = self.site_variable_cost * total_attendees
        
        # 3. Gate Net
        gate_net = total_gate_revenue - fixed_costs - total_variable
        
        # 4. Feast (Siloed)
        feast_rev = self.feast_fee * feast_count
        feast_exp = self.feast_cost_per_person * feast_count
        feast_net = feast_rev - feast_exp
        
        # 5. Beds (Siloed & Split)
        bed_rev = (self.beds_top_price * sold_top) + (self.beds_bot_price * sold_bot)
        bed_net = bed_rev
        
        total_net = gate_net + feast_net + bed_net
        
        # 6. Break Even (Gate Only)
        margin = self.ticket_weekend_member - self.site_variable_cost
        break_even = math.ceil(fixed_costs / margin) if margin > 0 else "N/A"

        return {
            "total_attendees": total_attendees,
            "total_revenue": total_gate_revenue + feast_rev + bed_rev,
            "total_expense": fixed_costs + total_variable + feast_exp,
            "gate_net": gate_net,
            "feast_net": feast_net,
            "bed_net": bed_net,
            "total_net": total_net,
            "break_even": break_even
        }

# ---------------------------------------------------------------------------
# PDF GENERATION
# ---------------------------------------------------------------------------
def export_to_pdf(bid: EventBid, projection: dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    elements.append(Paragraph("Kingdom of Meridies Event Bid", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    
    # Event Info
    elements.append(Paragraph(f"<b>Event:</b> {bid.event_name} ({bid.event_type})", styles["Normal"]))
    elements.append(Paragraph(f"<b>Group:</b> {bid.group_name}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Location:</b> {bid.site_name} - {bid.site_address}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Dates:</b> {bid.start_date} to {bid.end_date}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    # Site Features
    elements.append(Paragraph("<b>Site Features</b>", styles["Heading3"]))
    site_text = f"Parking: {bid.parking_spaces} spaces | Bathrooms: {bid.bathrooms_count}<br/>"
    if bid.camping_allowed:
        site_text += f"Camping: {bid.camping_tents} tent sites, {bid.camping_rv} RV sites<br/>"
    site_text += f"ADA: {'Ramps, ' if bid.ada_ramps else ''}Parking ({bid.ada_parking_count}), Bathrooms ({bid.ada_bathroom_count})"
    elements.append(Paragraph(site_text, styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    # Kitchen
    elements.append(Paragraph("<b>Kitchen Facilities</b>", styles["Heading3"]))
    k_text = f"Size: {bid.kitchen_size} ({bid.kitchen_sq_ft} sq ft)<br/>"
    k_text += f"Equipment: {bid.kitchen_stove_burners} Burners, {bid.kitchen_ovens} Ovens<br/>"
    k_text += f"Prep: {bid.kitchen_3bay_sinks} Sinks, {bid.kitchen_prep_tables} Tables<br/>"
    k_text += f"Cold Storage: {bid.kitchen_fridge_household} Fridges, {bid.kitchen_freezer_household} Freezers"
    elements.append(Paragraph(k_text, styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    # Pricing
    elements.append(Paragraph("<b>Gate Pricing</b>", styles["Heading3"]))
    p_text = f"Weekend Member: ${bid.ticket_weekend_member:.2f} (Non-Member: ${bid.ticket_weekend_member + bid.nms_surcharge:.2f})<br/>"
    p_text += f"Daytrip Member: ${bid.ticket_daytrip_member:.2f} (Non-Member: ${bid.ticket_daytrip_member + bid.nms_surcharge:.2f})<br/>"
    p_text += f"NMS Surcharge: ${bid.nms_surcharge:.2f} (pass-through to SCA Inc.)"
    elements.append(Paragraph(p_text, styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Lodging
    elements.append(Paragraph("<b>Lodging</b>", styles["Heading3"]))
    l_text = f"Top Bunks: {bid.beds_top_qty} available @ ${bid.beds_top_price:.2f} each<br/>"
    l_text += f"Bottom Bunks: {bid.beds_bot_qty} available @ ${bid.beds_bot_price:.2f} each"
    elements.append(Paragraph(l_text, styles["Normal"]))
    elements.append(Spacer(1, 12))
    
    # Expenses
    if bid.expenses:
        elements.append(Paragraph("<b>Operational Expenses</b>", styles["Heading3"]))
        exp_data = [["Item", "Projected", "Actual"]]
        for name, vals in bid.expenses.items():
            exp_data.append([name, f"${vals['projected']:.2f}", f"${vals['actual']:.2f}"])
        exp_table = Table(exp_data, colWidths=[200, 100, 100])
        exp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        elements.append(exp_table)
        elements.append(Spacer(1, 12))
    
    # Financial Projection
    elements.append(Paragraph("<b>Financial Projection</b>", styles["Heading3"]))
    data = [
        ["Category", "Amount"],
        ["Total Revenue", f"${projection['total_revenue']:.2f}"],
        ["Total Expense", f"${projection['total_expense']:.2f}"],
        ["Gate Net", f"${projection['gate_net']:.2f}"],
        ["Feast Net", f"${projection['feast_net']:.2f}"],
        ["Bed Net", f"${projection['bed_net']:.2f}"],
        ["NET PROFIT", f"${projection['total_net']:.2f}"],
        ["Gate Break Even", f"{projection['break_even']} Weekend Attendees"]
    ]
    t = Table(data, colWidths=[200, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,-2), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-2), (-1,-1), colors.yellow),
    ]))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Meridies Bidder", layout="wide", page_icon=KINGDOM_LOGO_URL)
    
    col_logo, col_title = st.columns([1, 6])
    with col_logo: st.image(KINGDOM_LOGO_URL, width=80)
    with col_title: 
        st.title("Kingdom of Meridies Event Bidder")
        st.caption("Budgeting Tool with Historical Site Database")

    if "bid" not in st.session_state:
        st.session_state.bid = EventBid()
    bid = st.session_state.bid

    # --- Sidebar ---
    with st.sidebar:
        st.header("📂 Actions")
        
        # Load Site
        site_choice = st.selectbox("Load Known Site", list(SITE_DATABASE.keys()))
        if site_choice != "Select a Site...":
            if st.button("Load Site Data"):
                bid.apply_site_profile(SITE_DATABASE[site_choice])
                bid.site_name = site_choice  # FIX: Set the site name explicitly
                st.success(f"Loaded {site_choice}")
                st.rerun()
        
        st.divider()
        
        # Upload JSON
        uploaded = st.file_uploader("Upload Bid JSON", type="json")
        if uploaded:
            data = json.load(uploaded)
            bid.load_data(data)
            st.success("Bid JSON Loaded")
            st.rerun()
        
        st.divider()
        
        # Reset Form
        if st.button("🔄 Reset Form", type="secondary"):
            st.session_state.bid = EventBid()
            st.success("Form reset!")
            st.rerun()

    # --- MAIN FORM ---
    
    # 1. Event Info
    st.subheader("1. Event Details")
    c1, c2, c3 = st.columns(3)
    bid.event_name = c1.text_input("Event Name", bid.event_name)
    bid.group_name = c2.text_input("Group/Branch Name", bid.group_name)
    event_type_idx = 0 if bid.event_type == "Local" else 1
    bid.event_type = c3.selectbox("Type", ["Local", "Kingdom"], index=event_type_idx)
    
    d1, d2, d3 = st.columns(3)
    bid.start_date = d1.date_input("Start Date", bid.start_date)
    bid.end_date = d2.date_input("End Date", bid.end_date)
    bid.is_single_day = d3.checkbox("Single Day Event?", bid.is_single_day)
    
    # Validation: Date order
    if bid.end_date < bid.start_date:
        st.warning("⚠️ End date is before start date!")

    # Site Location
    st.markdown("---")
    st.subheader("2. Site Information")
    s1, s2 = st.columns(2)
    bid.site_name = s1.text_input("Site Name", bid.site_name)
    bid.site_address = s2.text_input("Site Address", bid.site_address)
    
    s3, s4 = st.columns(2)
    bid.parking_spaces = s3.number_input("Parking Spaces", value=bid.parking_spaces, step=5)
    bid.bathrooms_count = s4.number_input("Bathrooms", value=bid.bathrooms_count, step=1)

    # 3. Staff
    st.markdown("---")
    st.subheader("3. Staffing")
    st1, st2 = st.columns(2)
    with st1:
        st.caption("Event Stewards")
        for i in range(2): 
            bid.event_stewards[i] = st.text_input(f"Autocrat {i+1}", bid.event_stewards[i], key=f"es{i}")
    with st2:
        st.caption("Feast Stewards")
        for i in range(2): 
            bid.feast_stewards[i] = st.text_input(f"Feastcrat {i+1}", bid.feast_stewards[i], key=f"fs{i}")

    # 4. Facilities
    st.markdown("---")
    st.subheader("4. Site Facilities")
    
    with st.expander("Camping & Lodging", expanded=False):
        camp1, camp2, camp3 = st.columns(3)
        bid.camping_allowed = camp1.checkbox("Camping Allowed", bid.camping_allowed)
        if bid.camping_allowed:
            bid.camping_tents = camp2.number_input("Tent Sites", value=bid.camping_tents, step=5)
            bid.camping_rv = camp3.number_input("RV Sites", value=bid.camping_rv, step=1)
    
    with st.expander("Kitchen Specs", expanded=True):
        k1, k2, k3, k4 = st.columns(4)
        kitchen_sizes = ["None", "Small", "Medium", "Large"]
        kitchen_idx = kitchen_sizes.index(bid.kitchen_size) if bid.kitchen_size in kitchen_sizes else 0
        bid.kitchen_size = k1.selectbox("Kitchen Size", kitchen_sizes, index=kitchen_idx)
        bid.kitchen_sq_ft = k2.number_input("Sq Ft", value=bid.kitchen_sq_ft, step=10)
        bid.kitchen_stove_burners = k3.number_input("Burners", value=bid.kitchen_stove_burners, step=1)
        bid.kitchen_ovens = k4.number_input("Ovens", value=bid.kitchen_ovens, step=1)
        
        k5, k6, k7 = st.columns(3)
        bid.kitchen_3bay_sinks = k5.number_input("3-Bay Sinks", value=bid.kitchen_3bay_sinks, step=1)
        bid.kitchen_prep_tables = k6.number_input("Prep Tables", value=bid.kitchen_prep_tables, step=1)
        bid.kitchen_garbage_cans = k7.number_input("Garbage Cans", value=bid.kitchen_garbage_cans, step=1)
        
        st.caption("Household Cold Storage")
        k8, k9 = st.columns(2)
        bid.kitchen_fridge_household = k8.number_input("Household Fridges", value=bid.kitchen_fridge_household, step=1)
        bid.kitchen_freezer_household = k9.number_input("Household Freezers", value=bid.kitchen_freezer_household, step=1)

    with st.expander("ADA & Accessibility", expanded=False):
        a1, a2, a3 = st.columns(3)
        bid.ada_ramps = a1.checkbox("Ramps Available", bid.ada_ramps)
        bid.ada_parking = a2.checkbox("ADA Parking", bid.ada_parking)
        bid.ada_bathrooms = a3.checkbox("ADA Bathrooms", bid.ada_bathrooms)
        
        a4, a5 = st.columns(2)
        bid.ada_parking_count = a4.number_input("Count of ADA Spots", value=bid.ada_parking_count, step=1)
        bid.ada_bathroom_count = a5.number_input("Count of ADA Stalls", value=bid.ada_bathroom_count, step=1)

    # 5. Financials
    st.markdown("---")
    st.subheader("5. Financials")
    
    # ROW 1: Site and NMS
    f1, f2, f3 = st.columns(3)
    bid.site_fee = f1.number_input("Site Rental Fee (Fixed)", value=bid.site_fee, min_value=0.0, step=10.0)
    bid.site_variable_cost = f2.number_input("Per Person Site Cost", value=bid.site_variable_cost, min_value=0.0, step=0.5)
    bid.nms_surcharge = f3.number_input("Non-Member Surcharge (NMS)", value=bid.nms_surcharge, min_value=0.0, step=1.0, 
                                        help="Pass-through fee to SCA Inc. - does not affect event budget")

    # ROW 2: Gate Prices with NMS Calc
    st.caption("Gate Pricing (Member rates used for break-even calculations)")
    gp1, gp2, gp3, gp4 = st.columns(4)
    bid.ticket_weekend_member = gp1.number_input("Adult Member Price", value=bid.ticket_weekend_member, min_value=0.0, step=1.0)
    gp2.metric("Adult Non-Member", f"${bid.ticket_weekend_member + bid.nms_surcharge:.2f}")
    
    bid.ticket_daytrip_member = gp3.number_input("Daytrip Member Price", value=bid.ticket_daytrip_member, min_value=0.0, step=1.0)
    gp4.metric("Daytrip Non-Member", f"${bid.ticket_daytrip_member + bid.nms_surcharge:.2f}")
    
    st.caption("Feast & Beds (Siloed Budgets)")
    fb1, fb2, fb3 = st.columns(3)
    bid.feast_fee = fb1.number_input("Feast Ticket Price", value=bid.feast_fee, min_value=0.0, step=1.0)
    bid.feast_cost_per_person = fb2.number_input("Feast Food Cost", value=bid.feast_cost_per_person, min_value=0.0, step=0.5)
    bid.feast_capacity = fb3.number_input("Feast Max Capacity", value=bid.feast_capacity, step=1)
    
    # BEDS UI
    st.write("**Cabin / Lodging Configuration**")
    b1, b2, b3, b4 = st.columns(4)
    bid.beds_top_qty = b1.number_input("Qty: Top Bunks", value=bid.beds_top_qty, step=1)
    bid.beds_top_price = b2.number_input("Price: Top ($)", value=bid.beds_top_price, min_value=0.0, step=1.0)
    bid.beds_bot_qty = b3.number_input("Qty: Bottom Bunks", value=bid.beds_bot_qty, step=1)
    bid.beds_bot_price = b4.number_input("Price: Bottom ($)", value=bid.beds_bot_price, min_value=0.0, step=1.0)

    # 6. Expenses
    st.markdown("---")
    st.subheader("6. Operational Expenses")
    
    # Add new expense
    e_col1, e_col2, e_col3 = st.columns([2, 1, 1])
    new_exp_name = e_col1.text_input("New Expense Item", key="new_exp_name")
    new_exp_cost = e_col2.number_input("Cost", 0.0, step=10.0, key="new_exp_cost")
    if e_col3.button("➕ Add Expense"):
        if new_exp_name:
            bid.expenses[new_exp_name] = {"projected": new_exp_cost, "actual": 0.0}
            st.success(f"Added: {new_exp_name}")
            st.rerun()
    
    # Display and manage existing expenses
    if bid.expenses:
        st.caption("Current Expenses")
        for exp_name in list(bid.expenses.keys()):
            exp_cols = st.columns([3, 2, 2, 1])
            exp_cols[0].text(exp_name)
            
            # Update projected/actual values
            new_proj = exp_cols[1].number_input(
                "Projected", 
                value=bid.expenses[exp_name]["projected"], 
                step=10.0, 
                key=f"proj_{exp_name}",
                label_visibility="collapsed"
            )
            new_actual = exp_cols[2].number_input(
                "Actual", 
                value=bid.expenses[exp_name]["actual"], 
                step=10.0, 
                key=f"actual_{exp_name}",
                label_visibility="collapsed"
            )
            
            # Update values if changed
            bid.expenses[exp_name]["projected"] = new_proj
            bid.expenses[exp_name]["actual"] = new_actual
            
            # Delete button
            if exp_cols[3].button("🗑️", key=f"del_{exp_name}"):
                del bid.expenses[exp_name]
                st.rerun()
    else:
        st.info("No expenses added yet. Add operational costs like insurance, supplies, etc.")

    # 7. Projections
    st.markdown("---")
    st.subheader("📊 Financial Projections")
    
    p1, p2, p3 = st.columns(3)
    proj_wk = p1.number_input("Projected Weekend Attendees", value=100, step=10)
    proj_dt = p2.number_input("Projected Daytrip Attendees", value=20, step=5)
    proj_fst = p3.number_input("Projected Feast Eaters", value=50, step=5)
    
    # Validation: Feast capacity
    if proj_fst > bid.feast_capacity and bid.feast_capacity > 0:
        st.warning(f"⚠️ Feast projections ({proj_fst}) exceed capacity ({bid.feast_capacity})!")
    
    p4, p5 = st.columns(2)
    sold_top = p4.number_input(
        f"Projected Top Beds Sold (Max: {bid.beds_top_qty})", 
        value=0, 
        max_value=bid.beds_top_qty, 
        step=1
    )
    sold_bot = p5.number_input(
        f"Projected Bottom Beds Sold (Max: {bid.beds_bot_qty})", 
        value=0, 
        max_value=bid.beds_bot_qty, 
        step=1
    )
    
    results = bid.calculate_projection(proj_wk, proj_dt, proj_fst, sold_top, sold_bot)
    
    # Display results with color coding
    r1, r2, r3 = st.columns(3)
    
    net_profit = results['total_net']
    if net_profit < 0:
        r1.metric("Net Profit", f"${net_profit:.2f}", delta="Loss", delta_color="inverse")
    else:
        r1.metric("Net Profit", f"${net_profit:.2f}", delta="Profit")
    
    r2.metric("Gate Break Even", f"{results['break_even']} attendees", 
              help="Weekend attendees needed to cover fixed costs (excl. feast/beds)")
    r3.metric("Total Expenses", f"${results['total_expense']:.2f}")
    
    with st.expander("Detailed Financial Breakdown"):
        detail_cols = st.columns(3)
        detail_cols[0].metric("Gate Net", f"${results['gate_net']:.2f}")
        detail_cols[1].metric("Feast Net", f"${results['feast_net']:.2f}")
        detail_cols[2].metric("Bed Net", f"${results['bed_net']:.2f}")
        
        st.json(results)

    # 8. Exports
    st.markdown("---")
    st.subheader("💾 Save & Submit")
    ex1, ex2 = st.columns(2)
    
    try:
        pdf_bytes = export_to_pdf(bid, results)
        ex1.download_button(
            "📄 Download PDF Report", 
            pdf_bytes, 
            f"bid_{bid.event_name.replace(' ', '_')}.pdf", 
            "application/pdf"
        )
    except Exception as e:
        ex1.error(f"PDF generation failed: {e}")
    
    json_str = json.dumps(bid.to_dict(), indent=4)
    ex2.download_button(
        "💾 Download Save File (.json)",
