import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import math
import pandas as pd
from datetime import datetime, time

# ==========================================
# CONFIGURATION & ASSETS
# ==========================================
# Link to the Kingdom of Meridies Arms (Public URL)
KINGDOM_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Arms_of_the_Kingdom_of_Meridies.svg/200px-Arms_of_the_Kingdom_of_Meridies.svg.png"

# ==========================================
# GOOGLE SHEETS DATABASE MANAGER
# ==========================================
def get_db_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Meridies_Event_Data").sheet1
    return sheet

def init_db(sheet):
    try:
        if not sheet.acell('A1').value:
            sheet.append_row(["Event Name", "Hosting Group", "Event Type", "Bid Data (JSON)"])
    except:
        pass 

def save_bid_to_sheet(event_name, group, event_type, bid_object):
    sheet = get_db_connection()
    init_db(sheet)
    
    bid_data = bid_object.to_dict()
    json_data = json.dumps(bid_data)
    
    records = sheet.get_all_records()
    row_index = None
    for idx, record in enumerate(records):
        if record['Event Name'] == event_name and record['Hosting Group'] == group:
            row_index = idx + 2 
            break
            
    if row_index:
        sheet.update_cell(row_index, 3, event_type)
        sheet.update_cell(row_index, 4, json_data)
        st.success(f"✅ Updated existing bid for {event_name}!")
    else:
        sheet.append_row([event_name, group, event_type, json_data])
        st.success(f"✅ Created new bid for {event_name}!")

def load_bid_from_sheet(event_name, group):
    try:
        sheet = get_db_connection()
        records = sheet.get_all_records()
        for record in records:
            if record['Event Name'] == event_name and record['Hosting Group'] == group:
                event_type = record['Event Type']
                data = json.loads(record['Bid Data (JSON)'])
                return event_type, data
        return None, None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None, None

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
        
        # ADA Accessibility (New)
        self.ada_ramps = False
        self.ada_parking = False
        self.ada_bathrooms = False
        
        # Kitchen
        self.kitchen_size = "None"
        self.kitchen_burners = 0
        self.kitchen_ovens = 0
        self.kitchen_amenities = [] 
        
        # Gate Pricing
        self.ticket_weekend_member = 0.0
        self.ticket_daytrip_member = 0.0
        self.nms_surcharge = 10.0
        
        # Feast
        self.feast_ticket_price = 0.0
        self.food_cost_per_person = 0.0 
        self.feast_capacity = 0
        
        # Lodging (Beds)
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
            'ada_bathrooms': self.ada_bathrooms,
            'kitchen_size': self.kitchen_size,
            'kitchen_burners': self.kitchen_burners,
            'kitchen_ovens': self.kitchen_ovens,
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
        self.ada_bathrooms = data.get('ada_bathrooms', False)
        
        self.kitchen_size = data.get('kitchen_size', "None")
        self.kitchen_burners = data.get('kitchen_burners', 0)
        self.kitchen_ovens = data.get('kitchen_ovens', 0)
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

    def get_total_fixed_costs(self, mode='projected'):
        total_ops = sum(item[mode] for item in self.expenses.values())
        return self.site_flat_fee + total_ops

    def calculate_bed_revenue(self, projected_occupancy_pct=1.0):
        top_rev = (self.beds_top_qty * projected_occupancy_pct) * self.beds_top_price
        bot_rev = (self.beds_bot_qty * projected_occupancy_pct) * self.beds_bot_price
        return top_rev + bot_rev

    def calculate_gate_break_even(self):
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
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("📂 File Management")
        input_event_name = st.text_input("Event Name")
        input_group_name = st.text_input("Hosting Group")
        
        if st.button("Load Bid from Cloud"):
            if not input_event_name or not input_group_name:
                st.error("⚠️ Error: You must enter both an Event Name and Hosting Group to load.")
            else:
                with st.spinner("Connecting..."):
                    etype, data = load_bid_from_sheet(input_event_name, input_group_name)
                    if data:
                        st.session_state['loaded_data'] = data
                        st.session_state['loaded_type'] = etype
                        st.success("Bid Loaded!")
                    else:
                        st.error("Bid not found. Check spelling or create a new one.")

    bid = EventBid()
    if 'loaded_data' in st.session_state:
        bid.load_data(st.session_state['loaded_data'])
        default_type_index = 0 if st.session_state['loaded_type'] == "KINGDOM" else 1
    else:
        default_type_index = 0

    # --- Main Form ---
    
    # 1. Event Type & Name
    st.subheader("1. Event Information")
    col_type, col_name = st.columns([1,2])
    
    with col_type:
        bid.event_type = st.selectbox("Event Type", ["KINGDOM", "LOCAL"], index=default_type_index)
        
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
            st.info("Event Name will be saved as 'Local Event'.")
            bid.kingdom_event_name = "Local Event"

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
    
    # NEW: ADA ACCESSIBILITY
    with st.expander("Accessibility (ADA)", expanded=True):
        st.caption("Select all that apply to this site:")
        ada_c1, ada_c2, ada_c3 = st.columns(3)
        bid.ada_ramps = ada_c1.checkbox("♿ Ramps / Level Access", value=bid.ada_ramps)
        bid.ada_parking = ada_c2.checkbox("🅿️ ADA Parking Available", value=bid.ada_parking)
        bid.ada_bathrooms = ada_c3.checkbox("🚻 ADA Accessible Bathrooms", value=bid.ada_bathrooms)

    with st.expander("Kitchen & Dining Amenities", expanded=False):
        k1, k2, k3 = st.columns(3)
        bid.kitchen_size = k1.selectbox("Kitchen Size", ["None", "Small", "Medium", "Large", "Giant"], index=0)
        bid.kitchen_burners = k2.number_input("Number of Burners/Gas Eyes", value=bid.kitchen_burners, min_value=0)
        bid.kitchen_ovens = k3.number_input("Number of Ovens", value=bid.kitchen_ovens, min_value=0)
        
        st.markdown("**Available Equipment:**")
        available_opts = [
            "Hobart Dishwasher", "Food Warmers", "Buffet Warming Table", 
            "Utensils/Pots/Pans", "Ice Machine", "Walk-in Fridge", "Freezer"
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
            m1.metric("Break Even (Full Price Heads)", res['break_even'] if res['break_even'] else "Impossible")
            m2.metric("Kingdom Share (50%)", f"${res['kingdom_share']:.2f}")
            m3.metric("Group Share", f"${res['group_share']:.2f}")
            m4.metric("Total Expenses", f"${res['total_expense']:.2f}")

            with st.expander("See Financial Breakdown"):
                st.write(f"**Gate Net:** ${res['gate_net']:.2f}")
                st.write(f"**Feast Net:** ${res['feast_net']:.2f}")
                st.write(f"**Bed/Cabin Net:** ${res['bed_net']:.2f}")
                if mode_key == 'actual':
                    st.info("Results based on ACTUALS column.")

    # Save
    st.markdown("---")
    if st.button("Save to Google Sheet"):
        if input_event_name and input_group_name:
            with st.spinner("Saving data..."):
                save_bid_to_sheet(input_event_name, input_group_name, bid.event_type, bid)
        else:
            st.error("⚠️ Error: Please enter an Event Name and Hosting Group in the Sidebar before saving.")

if __name__ == "__main__":
    main()
