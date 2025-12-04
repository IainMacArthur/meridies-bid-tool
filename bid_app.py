import streamlit as st
import sqlite3
import json
import math
import pandas as pd

# ==========================================
# DATABASE MANAGER
# ==========================================
def init_db():
    """Creates the database table if it doesn't exist."""
    conn = sqlite3.connect('event_bids.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT,
            hosting_group TEXT,
            event_type TEXT,
            data TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_bid_to_db(event_name, group, event_type, bid_object):
    """Saves the entire EventBid state as a JSON blob."""
    conn = sqlite3.connect('event_bids.db')
    c = conn.cursor()
    
    # Serialize the bid object data
    bid_data = {
        'fixed_costs': bid_object.fixed_costs, # Storing for backward compat
        'site_flat_fee': bid_object.site_flat_fee,
        'site_variable_cost': bid_object.site_variable_cost,
        'gate_ticket_price': bid_object.gate_ticket_price,
        'feast_ticket_price': bid_object.feast_ticket_price,
        'food_cost_per_person': bid_object.food_cost_per_person,
        'feast_capacity': bid_object.feast_capacity,
        'expenses': bid_object.expenses
    }
    
    json_data = json.dumps(bid_data)
    
    # Check if exists to update or insert
    c.execute("SELECT id FROM bids WHERE event_name=? AND hosting_group=?", (event_name, group))
    result = c.fetchone()
    
    if result:
        c.execute("UPDATE bids SET data=?, event_type=? WHERE id=?", (json_data, event_type, result[0]))
        st.success(f"Updated existing bid for {event_name}!")
    else:
        c.execute("INSERT INTO bids (event_name, hosting_group, event_type, data) VALUES (?, ?, ?, ?)",
                  (event_name, group, event_type, json_data))
        st.success(f"Created new bid for {event_name}!")
        
    conn.commit()
    conn.close()

def load_bid_from_db(event_name, group):
    """Loads a bid by name/group."""
    conn = sqlite3.connect('event_bids.db')
    c = conn.cursor()
    c.execute("SELECT event_type, data FROM bids WHERE event_name=? AND hosting_group=?", (event_name, group))
    result = c.fetchone()
    conn.close()
    
    if result:
        event_type = result[0]
        data = json.loads(result[1])
        return event_type, data
    return None, None

# ==========================================
# CORE LOGIC CLASS (Adapted for Web)
# ==========================================
class EventBid:
    def __init__(self):
        self.expenses = {} 
        self.event_type = "KINGDOM"
        self.site_flat_fee = 0.0
        self.site_variable_cost = 0.0
        self.gate_ticket_price = 0.0
        self.feast_ticket_price = 0.0
        self.food_cost_per_person = 0.0 
        self.feast_capacity = 0
        self.fixed_costs = 0.0 # Legacy container

    def load_data(self, data):
        """Populates the object from a dictionary (database load)."""
        self.site_flat_fee = data.get('site_flat_fee', 0.0)
        self.site_variable_cost = data.get('site_variable_cost', 0.0)
        self.gate_ticket_price = data.get('gate_ticket_price', 0.0)
        self.feast_ticket_price = data.get('feast_ticket_price', 0.0)
        self.food_cost_per_person = data.get('food_cost_per_person', 0.0)
        self.feast_capacity = data.get('feast_capacity', 0)
        self.expenses = data.get('expenses', {})

    def get_total_fixed_costs(self, mode='projected'):
        total_ops = sum(item[mode] for item in self.expenses.values())
        return self.site_flat_fee + total_ops

    def calculate_gate_break_even(self):
        margin = self.gate_ticket_price - self.site_variable_cost
        fixed_total = self.get_total_fixed_costs(mode='projected')
        if margin <= 0: return None 
        return math.ceil(fixed_total / margin)

    def generate_final_report(self, attendance, feast_count, mode='projected'):
        fixed_costs = self.get_total_fixed_costs(mode)
        gate_revenue = self.gate_ticket_price * attendance
        gate_expenses = fixed_costs + (self.site_variable_cost * attendance)
        general_net = gate_revenue - gate_expenses

        feast_revenue = self.feast_ticket_price * feast_count
        feast_expenses = self.food_cost_per_person * feast_count
        feast_net = feast_revenue - feast_expenses

        total_net = general_net + feast_net
        
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
            "general_net": general_net,
            "feast_net": feast_net
        }

# ==========================================
# STREAMLIT GUI
# ==========================================
def main():
    st.set_page_config(page_title="Meridies Bid Calculator", layout="wide")
    init_db()

    st.title("🛡️ Kingdom of Meridies Event Bidder")
    
    # --- Sidebar: Load/Save ---
    with st.sidebar:
        st.header("📂 File Management")
        st.markdown("Load or create a new bid by entering the details below.")
        
        input_event_name = st.text_input("Event Name")
        input_group_name = st.text_input("Hosting Group")
        
        if st.button("Load Bid"):
            etype, data = load_bid_from_db(input_event_name, input_group_name)
            if data:
                st.session_state['loaded_data'] = data
                st.session_state['loaded_type'] = etype
                st.success("Bid Loaded!")
            else:
                st.error("Bid not found.")

    # Initialize Bid Object
    bid = EventBid()
    
    # Check if we have loaded data in session
    if 'loaded_data' in st.session_state:
        bid.load_data(st.session_state['loaded_data'])
        default_type_index = 0 if st.session_state['loaded_type'] == "KINGDOM" else 1
    else:
        default_type_index = 0

    # --- Main Form ---
    
    # 1. Event Metadata
    col1, col2 = st.columns(2)
    with col1:
        event_type_sel = st.selectbox("Event Type", ["KINGDOM", "LOCAL"], index=default_type_index)
        bid.event_type = event_type_sel
    
    # 2. Site Costs
    st.subheader("1. Site & Gate Costs")
    c1, c2, c3 = st.columns(3)
    bid.site_flat_fee = c1.number_input("Site Flat Fee ($)", value=bid.site_flat_fee)
    bid.site_variable_cost = c2.number_input("Site Variable Cost (Total per person) ($)", value=bid.site_variable_cost)
    bid.gate_ticket_price = c3.number_input("Adult Weekend Ticket Price ($)", value=bid.gate_ticket_price)

    # 3. Line Items (Expenses)
    st.subheader("2. Operational Budget (Line Items)")
    st.caption("Add items like Prizes, Decorations, Insurance, etc.")
    
    # We use a dataframe editor for easier line item management
    # Convert dict to list for dataframe
    
    current_items = []
    for k, v in bid.expenses.items():
        current_items.append({"Item": k, "Projected": v['projected'], "Actual": v['actual']})
    
    if not current_items:
        current_items = [{"Item": "Example: Prizes", "Projected": 100.0, "Actual": 0.0}]

    df = pd.DataFrame(current_items)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    # Update bid object from edited dataframe
    bid.expenses = {}
    for index, row in edited_df.iterrows():
        if row["Item"] and row["Item"] != "Example: Prizes":
            bid.expenses[row["Item"]] = {
                'projected': float(row["Projected"]), 
                'actual': float(row["Actual"])
            }

    # 4. Feast
    st.subheader("3. Feast Details")
    f1, f2, f3 = st.columns(3)
    bid.feast_ticket_price = f1.number_input("Feast Ticket Price ($)", value=bid.feast_ticket_price)
    bid.food_cost_per_person = f2.number_input("Food Cost Limit Per Person ($)", value=bid.food_cost_per_person)
    bid.feast_capacity = f3.number_input("Feast Hall Capacity", value=int(bid.feast_capacity), step=1)

    # 5. Projections & Results
    st.markdown("---")
    st.subheader("📊 Financial Projections")
    
    p1, p2, p3 = st.columns(3)
    proj_attend = p1.number_input("Projected Gate Attendance", value=100, step=10)
    proj_feast = p2.number_input("Projected Feast Attendance", value=50, step=10)
    calc_mode = p3.selectbox("Calculation Mode", ["Projected Budget", "Post-Event Actuals"])
    
    mode_key = 'projected' if calc_mode == "Projected Budget" else 'actual'
    
    if st.button("Calculate Results", type="primary"):
        res = bid.generate_final_report(proj_attend, proj_feast, mode=mode_key)
        
        # Display Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Break Even Attendance", res['break_even'] if res['break_even'] else "Impossible")
        m2.metric("Total Profit", f"${res['total_net']:.2f}")
        m3.metric("Kingdom Share", f"${res['kingdom_share']:.2f}")
        m4.metric("Group Share", f"${res['group_share']:.2f}")
        
        # Detailed Breakdown
        st.write(f"**General Net:** ${res['general_net']:.2f} | **Feast Net:** ${res['feast_net']:.2f}")
        
        if mode_key == 'actual':
            st.info("Displaying results based on ACTUAL columns from the Line Items table.")

    # 6. Save Button
    st.markdown("---")
    if st.button("Save to Database"):
        if input_event_name and input_group_name:
            save_bid_to_db(input_event_name, input_group_name, bid.event_type, bid)
        else:
            st.error("Please enter an Event Name and Hosting Group in the Sidebar to save.")

if __name__ == "__main__":
    main()
