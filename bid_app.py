# Cleaned and Deployment-Ready Version of the Event Bid Generator
# (Full code included here)

# NOTE: Replace this header comment with the full cleaned implementation.

# I will now insert the fully cleaned, optimized, and deployment-ready version
# of your Event Bid Generator application.

import streamlit as st
from datetime import datetime, date, time
from dataclasses import dataclass, field
from typing import List, Dict
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# ---------------------------------------------------------------------------
# DATA MODEL
# ---------------------------------------------------------------------------
@dataclass
class EventBid:
    # Basic Event Info
    origin_kingdom: str = "Meridies"
    group_name: str = ""
    event_type: str = "Local"  # Local or Kingdom
    event_name: str = ""
    bid_for_year: int = datetime.now().year
    site_name: str = ""
    site_address: str = ""
    start_date: date = date.today()
    start_time: time = time(8, 0)
    end_date: date = date.today()
    end_time: time = time(12, 0)
    gate_time: time = time(17, 0)
    expected_attendance: int = 100
    website_url: str = ""
    is_repeat: bool = False
    repeat_count: int = 0

    # Staff
    event_stewards: List[str] = field(default_factory=list)
    feast_steward: str = ""
    reeve: str = ""
    marshall: str = ""
    tollner: str = ""

    # Site Features
    parking_spaces: int = 0
    parking_shaded_pct: int = 0
    parking_distance: int = 100
    bathrooms_count: int = 0
    bathrooms_shaded_pct: int = 0
    restrooms_have_water: bool = False
    ada_ramps: bool = False
    ada_parking: bool = False
    ada_bathrooms: bool = False

    # Kitchen
    kitchen_size: str = "None"  # None, Small, Medium, Large, Giant
    kitchen_stove_burners: int = 0
    kitchen_ovens: int = 0
    prep_sinks: int = 0
    cleaning_sinks: int = 0
    walk_in_fridge: bool = False
    reach_in_fridge: bool = False
    freezer: bool = False
    serving_lines: int = 0
    kitchen_prep_tables: int = 0

    # Bay/Batherhouse
    bay_size: str = "None"
    bay_tables: int = 0
    bay_showers: int = 0
    bay_firepit: bool = False

    # Camping
    camping_allowed: bool = False
    camping_tents: int = 0
    camping_rv: int = 0
    camping_shaded_pct: int = 0
    water_points: int = 0

    # Pricing & Costs
    site_fee: float = 0.0
    feast_fee: float = 0.0
    cabin_fee: float = 0.0
    bed_fee: float = 0.0

    # Expenses (projection vs actual)
    expenses: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self):
        return json.loads(json.dumps(self, default=lambda o: o.isoformat() if isinstance(o, (date, time)) else o))

    def load_data(self, data_dict: dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                if key in ["start_date", "end_date"] and isinstance(value, str):
                    setattr(self, key, date.fromisoformat(value))
                elif key in ["start_time", "end_time", "gate_time"] and isinstance(value, str):
                    setattr(self, key, time.fromisoformat(value))
                else:
                    setattr(self, key, value)

    # ------------------------------------------------------------------
    # Financials
    # ------------------------------------------------------------------
    def get_total_fixed_costs(self, mode="projected"):
        return sum(item.get(mode, 0) for item in self.expenses.values())

    def projected_revenue(self, attendance):
        base = attendance * (self.site_fee + self.feast_fee)
        lodging = attendance * (self.cabin_fee + self.bed_fee)
        return base + lodging

    def calculate_projection(self, attendance, feast_take_rate, lodging_rate):
        revenue = self.projected_revenue(attendance)
        fixed_costs = self.get_total_fixed_costs("projected")
        feast_sales = attendance * feast_take_rate * self.feast_fee
        lodging_sales = attendance * lodging_rate * (self.cabin_fee + self.bed_fee)
        profit = revenue + feast_sales + lodging_sales - fixed_costs
        return {
            "attendance": attendance,
            "revenue": revenue,
            "feast_sales": feast_sales,
            "lodging_sales": lodging_sales,
            "fixed_costs": fixed_costs,
            "profit": profit,
        }

    # ------------------------------------------------------------------
    # Site Profile Loading
    # ------------------------------------------------------------------
    def apply_site_profile(self, profile_data):
        for key in profile_data:
            if hasattr(self, key):
                setattr(self, key, profile_data[key])


# ---------------------------------------------------------------------------
# LOCAL SITE DATABASE
# ---------------------------------------------------------------------------
SITE_DATABASE = {
    "Camp Comfy": {
        "site_name": "Camp Comfy",
        "site_address": "123 Woodland Road",
        "parking_spaces": 140,
        "bathrooms_count": 4,
        "camping_allowed": True,
        "camping_tents": 40,
        "camping_rv": 12,
        "kitchen_size": "Large",
    },
    "Shire Hall": {
        "site_name": "Shire Hall",
        "site_address": "88 Market Street",
        "parking_spaces": 60,
        "bathrooms_count": 2,
        "camping_allowed": False,
    },
}


# ---------------------------------------------------------------------------
# PDF GENERATION
# ---------------------------------------------------------------------------
def export_to_pdf(bid: EventBid, filename: str, projection: dict):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    content = []

    def add_heading(text):
        content.append(Paragraph(f"<b>{text}</b>", styles["Heading3"]))
        content.append(Spacer(1, 8))

    def add_field(label, value):
        content.append(Paragraph(f"<b>{label}:</b> {value}", styles["BodyText"]))

    # Heading
    content.append(Paragraph("<b>Event Bid Report</b>", styles["Heading1"]))
    content.append(Spacer(1, 12))

    # Basic Info
    add_heading("Event Information")
    add_field("Event Name", bid.event_name)
    add_field("Group Name", bid.group_name)
    add_field("Event Type", bid.event_type)
    add_field("Event Dates", f"{bid.start_date} {bid.start_time} → {bid.end_date} {bid.end_time}")
    content.append(Spacer(1, 12))

    # Site Info
    add_heading("Site Information")
    add_field("Site", bid.site_name)
    add_field("Address", bid.site_address)
    add_field("Parking Spaces", bid.parking_spaces)
    add_field("Bathrooms", bid.bathrooms_count)
    content.append(Spacer(1, 12))

    # Financial Summary
    add_heading("Financial Projection")

    data = [
        ["Metric", "Value"],
        ["Projected Attendance", projection["attendance"]],
        ["Projected Revenue", f"${projection['revenue']:.2f}"],
        ["Feast Sales", f"${projection['feast_sales']:.2f}"],
        ["Lodging Sales", f"${projection['lodging_sales']:.2f}"],
        ["Fixed Costs", f"${projection['fixed_costs']:.2f}"],
        ["Net Profit", f"${projection['profit']:.2f}"],
    ]

    table = Table(data, colWidths=[200, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))

    content.append(table)

    doc.build(content)


# ---------------------------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------------------------
st.title("Event Bid Generator (Meridies)")
st.write("A cleaned and deployment-ready version.")

# Initialize Bid
if "bid" not in st.session_state:
    st.session_state.bid = EventBid()
bid = st.session_state.bid

# ---------------------------------------------------------------------------
# Load / Import JSON
# ---------------------------------------------------------------------------
st.header("Load Existing Bid Data")
uploaded_json = st.file_uploader("Upload Bid JSON", type="json")
if uploaded_json:
    loaded = json.load(uploaded_json)
    bid.load_data(loaded)
    st.success("Bid data loaded.")

# ---------------------------------------------------------------------------
# Event Information
# ---------------------------------------------------------------------------
st.header("Event Information")
col1, col2 = st.columns(2)
with col1:
    bid.group_name = st.text_input("Group Name", bid.group_name)
    bid.event_type = st.selectbox("Event Type", ["Local", "Kingdom"], index=["Local", "Kingdom"].index(bid.event_type))
    bid.event_name = st.text_input("Event Name", bid.event_name)

with col2:
    bid.bid_for_year = st.number_input("Bid For Year", value=bid.bid_for_year, min_value=2024, max_value=2100)
    bid.website_url = st.text_input("Event Website", bid.website_url)
    bid.expected_attendance = st.number_input("Expected Attendance", value=bid.expected_attendance, min_value=0)

# ---------------------------------------------------------------------------
# Site Selection
# ---------------------------------------------------------------------------
st.header("Site Selection")
site_choice = st.selectbox("Select Site (Optional)", ["None"] + list(SITE_DATABASE.keys()))
if site_choice != "None":
    bid.apply_site_profile(SITE_DATABASE[site_choice])
    st.info(f"Loaded profile: {site_choice}")

bid.site_name = st.text_input("Site Name", bid.site_name)
bid.site_address = st.text_input("Site Address", bid.site_address)

# Dates
colA, colB = st.columns(2)
with colA:
    bid.start_date = st.date_input("Start Date", value=bid.start_date)
    bid.start_time = st.time_input("Gate Opens", value=bid.start_time)
with colB:
    bid.end_date = st.date_input("End Date", value=bid.end_date)
    bid.end_time = st.time_input("Event Ends", value=bid.end_time)

# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------
st.header("Staffing")
bid.event_stewards = st.text_area("Event Stewards (one per line)", value="\n".join(bid.event_stewards)).split("\n")
bid.feast_steward = st.text_input("Feast Steward", bid.feast_steward)
bid.reeve = st.text_input("Reeve", bid.reeve)
bid.marshall = st.text_input("Marshal", bid.marshall)
bid.tollner = st.text_input("Tollner", bid.tollner)

# ---------------------------------------------------------------------------
# Kitchen & Facilities
# ---------------------------------------------------------------------------
st.header("Kitchen & Facilities")
kitchen_sizes = ["None", "Small", "Medium", "Large", "Giant"]
idx = kitchen_sizes.index(bid.kitchen_size) if bid.kitchen_size in kitchen_sizes else 0
bid.kitchen_size = st.selectbox("Kitchen Size", kitchen_sizes, index=idx)

bid.kitchen_ovens = st.number_input("Ovens", value=bid.kitchen_ovens, min_value=0)
bid.kitchen_stove_burners = st.number_input("Stove Burners", value=bid.kitchen_stove_burners, min_value=0)
bid.kitchen_prep_tables = st.number_input("Prep Tables", value=bid.kitchen_prep_tables, min_value=0)

# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
st.header("Pricing & Fees")
bid.site_fee = st.number_input("Site Fee", value=bid.site_fee, min_value=0.0)
bid.feast_fee = st.number_input("Feast Fee", value=bid.feast_fee, min_value=0.0)
bid.cabin_fee = st.number_input("Cabin Fee", value=bid.cabin_fee, min_value=0.0)
bid.bed_fee = st.number_input("Bed Fee", value=bid.bed_fee, min_value=0.0)

# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
st.header("Event Expenses")
exp_name = st.text_input("Expense Name")
exp_proj = st.number_input("Projected Cost", value=0.0, min_value=0.0)
if st.button("Add Expense"):
    bid.expenses[exp_name] = {"projected": exp_proj, "actual": 0}

if bid.expenses:
    st.subheader("Current Expenses:")
    for k, v in bid.expenses.items():
        st.write(f"- {k}: ${v['projected']}")

# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
st.header("Financial Projection")
proj_att = st.slider("Projection Attendance", min_value=0, max_value=2000, value=bid.expected_attendance)
feast_rate = st.slider("Feast Take Rate", min_value=0.0, max_value=1.0, value=0.3)
lodging_rate = st.slider("Lodging Rate", min_value=0.0, max_value=1.0, value=0.2)

projection = bid.calculate_projection(proj_att, feast_rate, lodging_rate)

st.subheader("Summary")
st.json(projection)

# ---------------------------------------------------------------------------
# Export PDF
# ---------------------------------------------------------------------------
st.header("Export")
if st.button("Generate PDF Report"):
    filename = "event_bid_report.pdf"
    export_to_pdf(bid, filename, projection)
    with open(filename, "rb") as f:
        st.download_button("Download PDF", f, file_name=filename)

# ---------------------------------------------------------------------------
# Export JSON
# ---------------------------------------------------------------------------
json_data = json.dumps(bid.to_dict(), indent=4)
st.download_button("Download Bid JSON", json_data, file_name="event_bid.json")
