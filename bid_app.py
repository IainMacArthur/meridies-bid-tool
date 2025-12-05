import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import math
import pandas as pd

# ==========================================
# GOOGLE SHEETS DATABASE MANAGER
# ==========================================
def get_db_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Ensure this matches your Google Sheet name exactly
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
    
    # Prepare Data
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
        self.expenses = {} 
        self.event_type = "KINGDOM"
        
        # Site Costs
        self.site_flat_fee = 0.0
        self.site_variable_cost = 0.0
        
        # Gate Pricing
        self.ticket_weekend_member = 0.0
        self.ticket_daytrip_member = 0.0
        self.nms_surcharge = 10.0 # Fixed as requested
        
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
            'site_flat_fee': self.site_flat_fee,
            'site_variable_cost': self.site_variable_cost,
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
        self.site_flat_fee = data.get('site_flat_fee', 0.0)
        self.site_variable_cost = data.get('site_variable_cost', 0.0)
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
        """Calculates revenue from beds based on a % sold assumption."""
        top_rev = (self.beds_top_qty * projected_occupancy_pct) * self.beds_top_price
        bot_rev = (self.beds_bot_qty * projected_occupancy_pct) * self.beds_bot_price
        return top_rev + bot_rev

    def calculate_gate_break_even(self):
        """
        Break even is calculated against the Weekend Member Price.
        Any profit from beds reduces the fixed cost burden.
        """
        margin = self.ticket_weekend_member - self.site_variable_cost
        
        # Bed revenue offsets fixed costs (assuming 100% sell out for break-even ideal)
        # Or should we be conservative and say 0% beds? 
        # Standard Bid Logic: Usually we check if Gate alone covers costs.
        fixed_total = self.get_total_fixed_costs(mode='projected')
        
        if margin <= 0: return None 
        return math.ceil(fixed_total / margin)

    def generate_final_report(self, attend_weekend, attend_daytrip, feast_count, bed_sell_pct, mode='projected'):
        fixed_costs = self.get_total_fixed_costs(mode)
        
        # 1. Gate Revenue (Excluding NMS)
        # We assume for revenue projection that these inputs are Member equivalents 
        # or that NMS is pass-through and ignored.
        rev_weekend = self.ticket_weekend_member * attend_weekend
        rev_daytrip = self.ticket_daytrip_member * attend_daytrip
        total_gate_revenue = rev_weekend + rev_daytrip
        
        # 2. Gate Variable Expenses
        total_attendees = attend_weekend + attend_daytrip
        total_variable = self.site_variable_cost * total_attendees
        
        gate_net = total_gate_revenue - fixed_costs - total_variable

        # 3. Feast Logic
        feast_revenue = self.feast_ticket_price * feast_count
        feast_expenses = self.food_cost_per_person * feast_count
        feast_net = feast_revenue - feast_expenses

        # 4. Bed Logic
        bed_revenue = self.calculate_bed_revenue(bed_sell_pct)
        # Assuming no specific variable cost per bed (laundry often in Ops budget)
        bed_net = bed_revenue 

        # 5. Totals
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
    st.set_page_config(page_title="Meridies Bid Calculator", layout="wide")

    st.title("🛡️ Kingdom of Meridies Event Bidder")
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("📂 File Management")
        input_event_name = st.text_input("Event Name")
        input_group_name = st.text_input("Hosting Group")
        
        if st.button("Load Bid from Cloud"):
            with st.spinner("Connecting..."):
                etype, data = load_bid_from_sheet(input_event_name, input_group_name)
                if data:
                    st.session_state['loaded_data'] = data
                    st.session_state['loaded_type'] = etype
                    st.success("Bid Loaded!")
                else:
                    st.error("Bid not found.")

    bid = EventBid()
    if 'loaded_data' in st.session_state:
        bid.load_data(st.session_state['loaded_data'])
        default_type_index = 0 if st.session_state['loaded_type'] == "KINGDOM" else 1
    else:
        default_type_index = 0

    # --- Main Form ---
    
    # 1. Event Type
    col_type, col_pad = st.columns([1,3])
    with col_type:
        bid.event_type = st.selectbox("Event Type", ["KINGDOM", "LOCAL"], index=default_type_index)

    # 2. Gate Pricing
    st.markdown("### 1. Gate Ticket Pricing")
    st.info(f"Note: The Non-Member Surcharge (NMS) is fixed at ${bid.nms_surcharge:.2f}. "
            "This calculator excludes NMS from profit calculations as it is a pass-through fee.")
    
    g1, g2, g3, g4 = st.columns(4)
    bid.ticket_weekend_member = g1.number_input("Weekend Member Price ($)", value=bid.ticket_weekend_member)
    bid.ticket_daytrip_member = g2.number_input("Daytrip Member Price ($)", value=bid.ticket_daytrip_member)
    
    # Display calculated Non-Member prices (Read Only)
    g3.metric("Weekend Non-Member", f"${bid.ticket_weekend_member + bid.nms_surcharge:.2f}")
    g4.metric("Daytrip Non-Member", f"${bid.ticket_daytrip_member + bid.nms_surcharge:.2f}")

    # 3. Site & Variable Costs
    st.markdown("---")
    st.markdown("### 2. Site Costs")
    
    sc1, sc2 = st.columns(2)
    bid.site_flat_fee = sc1.number_input("Site Flat Rental Fee ($)", value=bid.site_flat_fee)
    bid.site_variable_cost = sc2.number_input(
        "Variable Cost Per Person Per Day ($)", 
        value=bid.site_variable_cost,
        help="Leave as 0.00 unless the site charges a specific 'Head Tax' or per-person daily fee."
    )

    # 4. Lodging / Cabins
    st.markdown("---")
    st.markdown("### 3. Cabins & Lodging")
    with st.expander("Configure Bunks (If Applicable)", expanded=True):
        b1, b2, b3, b4 = st.columns(4)
        bid.beds_bot_qty = b1.number_input("Qty: Bottom Bunks", value=bid.beds_bot_qty, step=1)
        bid.beds_bot_price = b2.number_input("Price: Bottom Bunk ($)", value=bid.beds_bot_price)
        bid.beds_top_qty = b3.number_input("Qty: Top Bunks", value=bid.beds_top_qty, step=1)
        bid.beds_top_price = b4.number_input("Price: Top Bunk ($)", value=bid.beds_top_price)

    # 5. Operational Budget
    st.markdown("---")
    st.markdown("### 4. Operational Budget (Line Items)")
    
    current_items = []
    for k, v in bid.expenses.items():
        current_items.append({"Item": k, "Projected": v['projected'], "Actual": v['actual']})
    
    if not current_items:
        current_items = [{"Item": "Prizes", "Projected": 100.0, "Actual": 0.0}]

    df = pd.DataFrame(current_items)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    bid.expenses = {}
    for index, row in edited_df.iterrows():
        if row["Item"]:
            bid.expenses[row["Item"]] = {
                'projected': float(row["Projected"]), 
                'actual': float(row["Actual"])
            }

    # 6. Feast
    st.markdown("---")
    st.markdown("### 5. Feast Details")
    f1, f2, f3 = st.columns(3)
    bid.feast_ticket_price = f1.number_input("Feast Ticket Price (Revenue) ($)", value=bid.feast_ticket_price)
    bid.food_cost_per_person = f2.number_input("Food Cost Budget (Expense) ($)", value=bid.food_cost_per_person)
    bid.feast_capacity = f3.number_input("Feast Hall Capacity", value=int(bid.feast_capacity), step=1)

    # 7. Projections
    st.markdown("---")
    st.subheader("📊 Financial Projections")
    
    c1, c2, c3, c4 = st.columns(4)
    proj_weekend = c1.number_input("Projected Weekend Attendees", value=100, step=10)
    proj_daytrip = c2.number_input("Projected Daytrip Attendees", value=20, step=5)
    proj_feast = c3.number_input("Projected Feast Attendees", value=50, step=10)
    proj_beds = c4.slider("Projected Bed Sales %", 0.0, 1.0, 0.5, format="%d%%")
    
    calc_mode = st.radio("Calculation Mode", ["Projected Budget", "Post-Event Actuals"], horizontal=True)
    mode_key = 'projected' if calc_mode == "Projected Budget" else 'actual'

    if st.button("Calculate Results", type="primary"):
        res = bid.generate_final_report(proj_weekend, proj_daytrip, proj_feast, proj_beds, mode=mode_key)
        
        st.markdown(f"### Net Profit: :green[${res['total_net']:.2f}]")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Break Even (Weekend Heads)", res['break_even'] if res['break_even'] else "Impossible")
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
            st.error("Enter Event Name and Group in Sidebar.")

if __name__ == "__main__":
    main()
