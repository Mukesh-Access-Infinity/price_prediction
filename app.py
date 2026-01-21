import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime
from utils import (
    get_processed_data,
    unroll_agg,
    apply_gtn,
    DEFAULT_GTN_BY_COUNTRY,
    PPP_RATIONALE,
    reference_bucket,
    estimate_mfn_custom_product,
    load,
)
from typing import Optional

# Page configuration
st.set_page_config(
    page_title="Brand Price Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS to match React UI styling
st.markdown(
    """
<style>
    /* Main container styling */
    .main {
        background: #f0f4f8;
        padding: 0;
    }
    
    /* Header styling */
    .stApp header {
        background: #ffffff !important;
    }
    
    /* Remove padding from main block */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Card styling */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        border: 1px solid #e2e8f0;
    }
    
    /* Button styling */
    .stButton > button {
        background: #10b981 !important;
        color: white !important;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        border: none;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        background: #059669 !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
    }
    
    .stButton > button:disabled {
        background: rgba(156, 163, 175, 0.5) !important;
        color: rgba(255, 255, 255, 0.5) !important;
        box-shadow: none;
    }
    
    /* Multiselect styling */
    .stMultiSelect {
        background: white;
        border-radius: 8px;
    }
    
    /* Dataframe styling */
    .dataframe {
        font-size: 13px !important;
        border: 1px solid #e2e8f0;
    }
    
    .dataframe th {
        background: #ffffff !important;
        color: white !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        padding: 12px 8px !important;
        border-right: 2px solid rgba(255,255,255,0.3) !important;
        text-align: left !important;
    }
    
    .dataframe td {
        border-right: 2px solid #cbd5e1 !important;
        border-bottom: 1px solid #e2e8f0 !important;
        padding: 10px 8px !important;
        font-size: 13px !important;
    }
    
    .dataframe tr:hover {
        background-color: #f8fafc !important;
    }
    
    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Title styling */
    h1 {
        color: #1e293b !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }
    
    h3 {
        color: #1e293b !important;
        font-weight: 700 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Initialize session state for GTN toggle and custom GTN values
if "gtn_enabled" not in st.session_state:
    st.session_state.gtn_enabled = False
if "custom_gtn_values" not in st.session_state:
    st.session_state.custom_gtn_values = DEFAULT_GTN_BY_COUNTRY.copy()
if "wac_prices" not in st.session_state:
    st.session_state.wac_prices = {}  # Format: {(brand, country, pack): wac_value}
if "custom_exchange_rates" not in st.session_state:
    st.session_state.custom_exchange_rates = {}
if "custom_ppp_rates" not in st.session_state:
    st.session_state.custom_ppp_rates = {}
if "selected_brands" not in st.session_state:
    st.session_state.selected_brands = []  # Support multiple brands
if "additional_markets_data" not in st.session_state:
    st.session_state.additional_markets_data = {}

# Version counters for widget key versioning (enables proper reset)
if "gtn_version" not in st.session_state:
    st.session_state.gtn_version = 0
if "fx_version" not in st.session_state:
    st.session_state.fx_version = 0
if "ppp_version" not in st.session_state:
    st.session_state.ppp_version = 0
if "additional_markets_version" not in st.session_state:
    st.session_state.additional_markets_version = 0



# Load data once at startup
@st.cache_data
def get_data():
    """Load data from get_processed_data"""
    r = get_processed_data(refresh=False)
    if not isinstance(r, list):
        raise ValueError(r)
    return r


@st.cache_data
def fetch_filter_options():
    """Get available filter options from data"""
    try:
        data = get_data()
        brands = sorted(set([item["Brand Name"] for item in data]))
        countries = sorted(set([item["Country"] for item in data]))
        return {
            "brands": brands,
            "countries": countries,
            "assumptions": {
                "sources": {"pack_prices": "NURO", "ppp": "OECD/WHO"},
                "ppp_rationale": PPP_RATIONALE,
                "gtn_defaults": DEFAULT_GTN_BY_COUNTRY,
                "reference_basket": reference_bucket,
            },
        }
    except Exception as e:
        st.error(f"Failed to fetch filter options: {str(e)}")
        return {"brands": [], "countries": [], "assumptions": {}}


@st.cache_data
def fetch_brand_specific_filters(brand: str):
    """Get countries and packs for a specific brand"""
    try:
        data = get_data()
        brand_data = [item for item in data if item["Brand Name"] == brand]

        countries = sorted(set([item["Country"] for item in brand_data]))
        packs = sorted(set([item["Pack"] for item in brand_data]))

        return {"countries": countries, "packs": packs}
    except Exception as e:
        st.error(f"Failed to fetch brand filters: {str(e)}")
        return {"countries": [], "packs": []}


def fetch_packs_for_countries(brand: str, countries: list):
    """Get packs available for specific countries"""
    try:
        data = get_data()
        brand_data = [item for item in data if item["Brand Name"] == brand]

        if countries:
            # Filter by selected countries
            brand_data = [item for item in brand_data if item["Country"] in countries]

        packs = sorted(set([item["Pack"] for item in brand_data]))
        return packs
    except Exception as e:
        st.error(f"Failed to fetch packs: {str(e)}")
        return []


def fetch_countries_for_packs(brand: str, packs: list):
    """Get countries available for specific packs"""
    try:
        data = get_data()
        brand_data = [item for item in data if item["Brand Name"] == brand]

        if packs:
            # Filter by selected packs
            brand_data = [item for item in brand_data if item["Pack"] in packs]

        countries = sorted(set([item["Country"] for item in brand_data]))
        return countries
    except Exception as e:
        st.error(f"Failed to fetch countries: {str(e)}")
        return []


def apply_gtn_to_agg(agg_data: list, gtn_map: dict) -> list:
    """Apply GTN to aggregated data by converting to long, applying GTN, and reconstructing."""
    df = unroll_agg(agg_data)
    if df.empty:
        return agg_data
    
    # Create net price columns
    for col in ["cost_per_unit", "usd_price_per_unit", "ppp_price_per_unit", "ppp_price"]:
        if col in df.columns:
            gtn_series = df["country"].str.lower().map(gtn_map).fillna(0.0)
            factor = 1.0 - gtn_series
            df[f"net_{col}"] = df[col] * factor
    
    # Recompute MFN on gross PPP (original)
    if "ppp_price" in df.columns:
        df["mfn_price"] = df.groupby(["year", "brand_name"])["ppp_price"].transform(
            lambda x: x.nsmallest(2).max() if len(x.dropna()) >= 1 else float("nan")
        )
    
    # Recompute MFN on net PPP (new)
    if "net_ppp_price" in df.columns:
        df["net_mfn_price"] = df.groupby(["year", "brand_name"])["net_ppp_price"].transform(
            lambda x: x.nsmallest(2).max() if len(x.dropna()) >= 1 else float("nan")
        )
    
    # Reconstruct aggregated format
    result = []
    for (brand, country, form), g in df.groupby(["brand_name", "country", "form"], sort=False):
        year_dict = {}
        for _, row in g.iterrows():
            year = int(row["year"])
            year_dict[year] = {
                "Cost Per Unit Local": row.get("cost_per_unit"),
                "Cost Per Unit USD": row.get("usd_price_per_unit"),
                "Cost Per Unit PPP": row.get("ppp_price_per_unit"),
                "MFN Price USD": row.get("mfn_price"),
                "Net Cost Per Unit USD": row.get("net_usd_price_per_unit"),
                "Net PPP Price": row.get("net_ppp_price_per_unit"),
                "Net MFN Price": row.get("net_mfn_price"),
            }
        result.append(
            {
                "Brand Name": brand,
                "Country": country.title(),
                "Pack": form,
                "Year": year_dict,
            }
        )
    return result


def fetch_data(
    brands: Optional[list] = None,
    countries: Optional[list] = None,
    packs: Optional[list] = None,
    apply_gtn_flag: bool = False,
    wac_map: Optional[dict] = None,
) -> dict:
    """Fetch and filter data for one or more brands"""
    try:
        all_data = get_data()

        if not brands or len(brands) == 0:
            return {
                "table1": pd.DataFrame(),
                "table2": pd.DataFrame(),
                "table3": pd.DataFrame(),
            }

        # Filter data for selected brands (support multiple)
        brand_data = [item for item in all_data if item["Brand Name"] in brands]

        if not brand_data:
            return {
                "table1": pd.DataFrame(),
                "table2": pd.DataFrame(),
                "table3": pd.DataFrame(),
            }

        # Apply user-entered exchange rate overrides (recompute USD values from local)
        if st.session_state.custom_exchange_rates:
            for item in brand_data:
                country_key = item["Country"].lower()
                ex_override = st.session_state.custom_exchange_rates.get(country_key)
                if ex_override is None:
                    continue
                for year, metrics in item["Year"].items():
                    local_val = metrics.get("Cost Per Unit Local")
                    if local_val is not None:
                        metrics["Cost Per Unit USD"] = local_val * ex_override

        # Apply GTN if enabled
        if apply_gtn_flag:
            brand_data = apply_gtn_to_agg(brand_data, st.session_state.custom_gtn_values)

        # Collect all years to ensure consistent columns
        all_years = set()
        for item in brand_data:
            all_years.update(item["Year"].keys())
        all_years = sorted(all_years)

        # Build Table 1: Country, Pack, Cost Per Unit (Local), Cost Per Unit (USD) - Year Wise
        table1_rows = []
        # Build Table 2: Country, Pack, Cost Per Unit (USD), Cost Per Unit (PPP) - Year Wise
        table2_rows = []
        # Build Table 3: Country, Pack, Cost Per Unit (USD), MFN Price (USD) - Year Wise
        table3_rows = []

        # Collect all packs in the filtered set (for US MFN table completeness)
        filtered_packs = set(
            [
                item["Pack"]
                for item in brand_data
                if (not packs or item["Pack"] in packs)
            ]
        )
        us_rows_by_pack = {}

        for item in brand_data:
            brand_name = item["Brand Name"]
            country = item["Country"]
            pack = item["Pack"]
            year_data = item["Year"]

            # Apply filters
            country_filter_match = not countries or country in countries
            pack_filter_match = not packs or pack in packs

            # Prepare row for table 1
            row1 = {"Brand": brand_name, "Country": country, "Pack": pack}
            # Prepare row for table 2
            row2 = {"Brand": brand_name, "Country": country, "Pack": pack}
            # Prepare row for table 3
            row3 = {"Brand": brand_name, "Country": country, "Pack": pack}

            for year in all_years:
                metrics = year_data.get(year, {})
                # Table 1 columns
                if country.lower() != "united states of america":
                    row1[(year, "Local Price")] = metrics.get(
                        "Cost Per Unit Local", None
                    )
                    row1[(year, "USD Price")] = metrics.get("Cost Per Unit USD", None)
                    if apply_gtn_flag:
                        row1[(year, "Net USD Price")] = metrics.get(
                            "Net Cost Per Unit USD", None
                        )

                    # Table 2 columns
                    row2[(year, "USD Price")] = metrics.get("Cost Per Unit USD", None)
                    row2[(year, "PPP Adjusted Price")] = metrics.get(
                        "Cost Per Unit PPP", None
                    )
                    if apply_gtn_flag:
                        row2[(year, "Net PPP Price")] = metrics.get(
                            "Net PPP Price", None
                        )
                else:
                    # Table 3 columns (US - MFN)
                    row3[(year, "USD Price")] = metrics.get("Cost Per Unit USD", None)
                    row3[(year, "MFN Price")] = metrics.get("MFN Price USD", None)
                if apply_gtn_flag:
                    row3[(year, "Net MFN Price")] = metrics.get("Net MFN Price", None)
                    
                    # Add WAC and differential if available
                    if wac_map:
                        wac_key = (brand_name.lower(), pack.lower())
                        if wac_key in wac_map:
                            wac_val = wac_map[wac_key]
                            row3[(year, "WAC Price")] = wac_val
                            
                            # Calculate differential % (MFN vs WAC)
                            mfn_val = metrics.get("MFN Price USD")
                            if mfn_val and wac_val and wac_val > 0:
                                diff_pct = ((mfn_val - wac_val) / wac_val) * 100
                                row3[(year, "MFN vs WAC %")] = diff_pct
                            
                            # If GTN enabled, also calc net differential (using net MFN)
                            if apply_gtn_flag:
                                net_mfn = metrics.get("Net MFN Price")
                                if net_mfn and wac_val and wac_val > 0:
                                    net_diff_pct = ((net_mfn - wac_val) / wac_val) * 100
                                    row3[(year, "Net vs WAC %")] = net_diff_pct
            if country.lower() != "united states of america":
                if country_filter_match and pack_filter_match:
                    table1_rows.append(row1)
                    table2_rows.append(row2)
            else:
                if pack_filter_match:
                    us_rows_by_pack[pack] = row3

        # For US MFN table: ensure all filtered packs are present, even if not in US data
        for pack in filtered_packs:
            if pack in us_rows_by_pack:
                table3_rows.append(us_rows_by_pack[pack])
            # Uncomment to include missing US price packs as well
            # else:
            #     # Create empty row for missing pack
            #     empty_row = {"Country": "United States of America", "Pack": pack}
            #     for year in all_years:
            #         empty_row[(year, "USD Price")] = None
            #         empty_row[(year, "MFN Price")] = None
            #     table3_rows.append(empty_row)

        # Create DataFrames with multi-index columns
        df1 = pd.DataFrame(table1_rows)
        df2 = pd.DataFrame(table2_rows)
        df3 = pd.DataFrame(table3_rows)

        # Separate basic columns from year columns
        basic_cols = ["Brand", "Country", "Pack"]

        # Create proper multi-index for table 1
        if not df1.empty:
            year_cols1 = [col for col in df1.columns if col not in basic_cols]
            # Create new column structure
            new_cols1 = [("", col) for col in basic_cols] + year_cols1
            df1.columns = pd.MultiIndex.from_tuples(new_cols1)

        # Create proper multi-index for table 2
        if not df2.empty:
            year_cols2 = [col for col in df2.columns if col not in basic_cols]
            # Create new column structure
            new_cols2 = [("", col) for col in basic_cols] + year_cols2
            df2.columns = pd.MultiIndex.from_tuples(new_cols2)

        # Create proper multi-index for table 3
        if not df3.empty:
            year_cols3 = [col for col in df3.columns if col not in basic_cols]
            # Create new column structure
            new_cols3 = [("", col) for col in basic_cols] + year_cols3
            df3.columns = pd.MultiIndex.from_tuples(new_cols3)

        return {"table1": df1, "table2": df2, "table3": df3}
    except Exception as e:
        st.error(f"Failed to fetch data: {str(e)}")
        return {
            "table1": pd.DataFrame(),
            "table2": pd.DataFrame(),
            "table3": pd.DataFrame(),
        }


def export_to_excel(brands, countries=None, packs=None, include_gtn=False, gtn_map=None, wac_map=None):
    """Generate Excel export for one or more brands"""
    if gtn_map is None:
        gtn_map = DEFAULT_GTN_BY_COUNTRY
    if wac_map is None:
        wac_map = {}
    
    # Ensure brands is a list
    if isinstance(brands, str):
        brands = [brands]
    
    try:
        result = fetch_data(brands=brands, countries=countries, packs=packs, apply_gtn_flag=include_gtn, wac_map=wac_map)

        # Create Excel file with all tables
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            # Write Table 1
            df1 = result["table1"].copy()
            if not df1.empty:
                # Flatten MultiIndex columns for Excel export
                if isinstance(df1.columns, pd.MultiIndex):
                    df1.columns = [
                        f"{col[0]} - {col[1]}" if col[0] else col[1]
                        for col in df1.columns
                    ]
                df1.to_excel(writer, index=False, sheet_name="Local vs USD")

            # Write Table 2
            df2 = result["table2"].copy()
            if not df2.empty:
                # Flatten MultiIndex columns for Excel export
                if isinstance(df2.columns, pd.MultiIndex):
                    df2.columns = [
                        f"{col[0]} - {col[1]}" if col[0] else col[1]
                        for col in df2.columns
                    ]
                df2.to_excel(writer, index=False, sheet_name="USD vs PPP")

            # Write Table 3
            df3 = result["table3"].copy()
            if not df3.empty:
                # Flatten MultiIndex columns for Excel export
                if isinstance(df3.columns, pd.MultiIndex):
                    df3.columns = [
                        f"{col[0]} - {col[1]}" if col[0] else col[1]
                        for col in df3.columns
                    ]
                df3.to_excel(writer, index=False, sheet_name="US - MFN with WAC")

            # Write Assumptions
            assumptions_rows = [
                ["Pack prices source", "NURO"],
                ["PPP source", "OECD/WHO"],
                ["PPP rationale", PPP_RATIONALE],
                ["Reference basket", ", ".join(reference_bucket)],
                ["GTN applied", str(include_gtn)],
            ]
            
            # Add custom GTN values if applied
            if include_gtn and gtn_map:
                for country, rate in sorted(gtn_map.items()):
                    assumptions_rows.append([f"GTN% - {country.title()}", f"{rate * 100:.1f}%"])
            elif not include_gtn:
                assumptions_rows.append(["GTN% - (Not Applied)", "-"])
            
            # Add WAC values if provided
            if wac_map:
                assumptions_rows.append(["", ""])  # Blank row
                for (brand_key, pack_key), wac_val in sorted(wac_map.items()):
                    assumptions_rows.append([f"WAC - {brand_key} / {pack_key}", f"${wac_val:.2f}"])

            pd.DataFrame(assumptions_rows, columns=["Item", "Value"]).to_excel(
                writer, index=False, sheet_name="Assumptions"
            )

        output.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brand_names = "_".join(brands) if len(brands) <= 2 else f"{len(brands)}_brands"
        return output.getvalue(), f"price_data_{brand_names}_{timestamp}.xlsx"
    except Exception as e:
        st.error(f"Export failed: {str(e)}")
        return None, None


def style_dataframe(df: pd.DataFrame):
    """Apply styling to dataframe"""

    if df.empty:
        return df
    ppp_col = [col for col in df.columns if "ppp" in str(col).lower()][0]
    mfn_price = df[ppp_col].replace("-", 0).astype(float).nsmallest(2).max()

    def apply_styles(row):
        styles = []
        value = row[ppp_col]
        if value == mfn_price:
            styles.append("background-color: #dbeafe; font-weight: 600; color: #1e293b")
        return styles

    return df.style.apply(apply_styles, axis=1)


def format_value(value):
    """Format numeric values for display"""
    if pd.isna(value) or value == 0 or value == 0.0:
        return "-"
    try:
        return f"{float(value):.2f}"
    except:
        return str(value)


def create_display_table(df):
    """Format DataFrame for display"""
    if df.empty:
        return df

    # Format numeric columns (those with year-based multi-index)
    for col in df.columns:
        if isinstance(col, tuple) and col[0] != "":  # Year-based columns
            df[col] = df[col].apply(format_value)

    return df


# Main app
def main():
    # Custom header
    st.markdown(
        """
    <div style='background: #ffffff; 
                padding: 1.5rem 2rem; 
                border-bottom: 3px solid rgba(255,255,255,0.1);
                margin: -2rem -2rem 2rem -2rem;
                border-radius: 0;'>
        <h1 style='color: white; margin: 0; font-weight: 700; letter-spacing: -0.5px;'>
            Brand Price Dashboard
        </h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Apply any pending reset flags BEFORE widgets are instantiated
    # (Reset flags removed - now handled directly in button callbacks)

    # Fetch filter options
    filter_options = fetch_filter_options()

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown(
                """
            <h5 style='margin: 0 0 1rem 0; color: #1e293b; font-weight: 700;'>Select Brand(s)</h5>
            """,
                unsafe_allow_html=True,
            )

            # Multiple select dropdown for brands
            selected_brands = st.multiselect(
                label="Choose brand(s) to view data",
                options=filter_options.get("brands", []),
                placeholder="Select one or more brands...",
                label_visibility="collapsed",
                key="selected_brands_input",
            )
            # For backward compatibility with single brand logic
            selected_brand = selected_brands[0] if selected_brands else None

        with col2:
            st.markdown(
                """
            <h3 style='margin: 0 0 1rem 0; color: #1e293b; font-weight: 700; font-size: 14px;'>Markets</h3>
            """,
                unsafe_allow_html=True,
            )
            all_country_options = filter_options.get("countries", [])
            if st.session_state.additional_markets_data:
                all_country_options = sorted(
                    set(all_country_options)
                    | {m.title() for m in st.session_state.additional_markets_data.keys()}
                )

            preset_selection = st.session_state.get("selected_countries_filter", [])

            # if st.button("Clear markets", key="clear_markets_btn"):
            #     preset_selection = []
            #     st.session_state.selected_countries_filter = []
            #     st.rerun()

            selected_countries = st.multiselect(
                label="Filter by countries",
                options=all_country_options,
                default=preset_selection,
                placeholder="All markets",
                label_visibility="collapsed",
                key="selected_countries_filter",
            )

        with col3:
            st.markdown(
                """
            <h3 style='margin: 0 0 1rem 0; color: #1e293b; font-weight: 700; font-size: 14px;'>Settings</h3>
            """,
                unsafe_allow_html=True,
            )
            st.session_state.gtn_enabled = st.toggle(
                "Apply GTN",
                value=st.session_state.gtn_enabled,
                help="Show net prices (gross to net) alongside gross prices",
            )

    # GTN % Editor (only show when GTN enabled)
    if st.session_state.gtn_enabled:
        with st.expander("Edit GTN% by Market", expanded=False):
            st.markdown(
                "Adjust gross-to-net percentages per market (override defaults). "
                "Enter as percentage (e.g., 40 for 40%)."
            )

            # Create columns for market inputs (3 per row)
            markets = list(DEFAULT_GTN_BY_COUNTRY.keys())
            cols_per_row = 3
            num_rows = (len(markets) + cols_per_row - 1) // cols_per_row

            for row_idx in range(num_rows):
                cols = st.columns(cols_per_row)
                for col_idx, col in enumerate(cols):
                    market_idx = row_idx * cols_per_row + col_idx
                    if market_idx < len(markets):
                        market = markets[market_idx]
                        # Always use DEFAULT as the source of truth, not session_state
                        default_from_constant = DEFAULT_GTN_BY_COUNTRY.get(market, 0) * 100
                        with col:
                            val = st.number_input(
                                label=market.title(),
                                value=default_from_constant,
                                min_value=0.0,
                                max_value=100.0,
                                step=0.1,
                                format="%.2f",
                                key=f"gtn_input_{market}_{st.session_state.gtn_version}",
                                help=f"GTN% for {market.title()}",
                            )
                            # Store as fraction (0.0 to 1.0)
                            st.session_state.custom_gtn_values[market] = val / 100.0

            # Reset button
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Reset to Defaults", key="reset_gtn_btn"):
                    st.session_state.custom_gtn_values = DEFAULT_GTN_BY_COUNTRY.copy()
                    st.session_state.gtn_version += 1
                    st.rerun()

    # Additional Markets Support
    with st.expander("Add Additional Markets (Beyond GENEROUS)", expanded=False):
        st.markdown(
            "Add additional countries for MFN estimation beyond the 8 GENEROUS reference markets. "
            "This expands the pricing basket for more comprehensive analysis."
        )
        
        additional_market_name = st.text_input(
            "Country/Market Name",
            placeholder="e.g., Australia, Mexico",
            key="additional_market_input"
        ).strip()
        
        if additional_market_name:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                exchange_rate = st.number_input(
                    "Exchange Rate (to USD)",
                    value=1.0,
                    step=0.000001,
                    format="%.6f",
                    key=f"ex_rate_{additional_market_name}"
                )
            with col2:
                ppp_rate = st.number_input(
                    "PPP Rate",
                    value=1.0,
                    step=0.000001,
                    format="%.6f",
                    key=f"ppp_{additional_market_name}"
                )
            with col3:
                st.markdown("")  # Spacing
                if st.button("Add Market", key=f"add_market_{additional_market_name}"):
                    normalized_name = additional_market_name.title()
                    st.session_state.additional_markets_data[normalized_name] = {
                        "exchange_rate": exchange_rate,
                        "ppp_rate": ppp_rate
                    }
                    st.success(f"Added {normalized_name}")
                    st.rerun()
        
        # Display added markets
        if st.session_state.additional_markets_data:
            st.markdown("**Added Markets:**")
            for market, data in st.session_state.additional_markets_data.items():
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.write(f"{market}")
                with col2:
                    st.write(f"Ex Rate: {data['exchange_rate']:.2f}")
                with col3:
                    st.write(f"PPP: {data['ppp_rate']:.4f}")
                with col4:
                    if st.button("❌", key=f"remove_{market}", help=f"Remove {market}"):
                        del st.session_state.additional_markets_data[market]
                        st.rerun()
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Clear All", key="clear_additional_markets"):
                    st.session_state.additional_markets_data = {}
                    st.session_state.additional_markets_version += 1
                    st.rerun()

    # Conversion Rates Editor (always show for sensitivity analysis)
    with st.expander("Edit Exchange Rates (Sensitivity Analysis)", expanded=False):
        st.markdown(
            "Adjust exchange rates (LCU to USD) for sensitivity analysis. Leave blank to use default rates."
        )

        # Load default exchange rates from processed data
        try:
            processed_data = load("processed_price_data")
            if not processed_data.empty:
                default_rates = processed_data.groupby("country")["exchange_rate"].first().to_dict()
            else:
                default_rates = {}
        except:
            default_rates = {}

        # Create columns for market inputs (3 per row)
        markets_base = [c.lower() for c in selected_countries] if selected_countries else reference_bucket
        markets_extra = [m.lower() for m in st.session_state.additional_markets_data.keys()]
        markets = sorted(set(markets_base) | set(markets_extra))
        cols_per_row = 3
        num_rows = (len(markets) + cols_per_row - 1) // cols_per_row

        for row_idx in range(num_rows):
            cols = st.columns(cols_per_row)
            for col_idx, col in enumerate(cols):
                market_idx = row_idx * cols_per_row + col_idx
                if market_idx < len(markets):
                    market = markets[market_idx]
                    market_lower = market.lower()
                    # Always use data default as source of truth
                    data_default = default_rates.get(market_lower, 1.0)
                    with col:
                        val = st.number_input(
                            label=f"{market.title()} to USD",
                            value=data_default,
                            step=0.000001,
                            format="%.6f",
                            key=f"ex_rate_input_{market_lower}_{st.session_state.fx_version}",
                            help=f"Exchange rate for {market.title()}",
                        )
                        # Store if different from default (use tolerance for float comparison)
                        if abs(val - data_default) > 0.0001:
                            st.session_state.custom_exchange_rates[market_lower] = val
                        elif market_lower in st.session_state.custom_exchange_rates:
                            del st.session_state.custom_exchange_rates[market_lower]

        # Reset button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Reset Rates to Defaults", key="reset_ex_rates_btn"):
                st.session_state.custom_exchange_rates = {}
                st.session_state.fx_version += 1
                st.rerun()

    # PPP Values Editor (always show for sensitivity analysis)
    with st.expander("Edit PPP Values (Sensitivity Analysis)", expanded=False):
        st.markdown(
            "Adjust health-specific PPP rates for sensitivity analysis. Leave blank to use default values."
        )

        # Load default PPP rates from processed data
        try:
            ppp_data = load("ppp_2020_2023")
            if not ppp_data.empty and "2023" in ppp_data.columns:
                default_ppp = ppp_data.set_index("country")["2023"].to_dict()
            else:
                default_ppp = {}
        except:
            default_ppp = {}

        # Create columns for market inputs (3 per row)
        markets_base = [c.lower() for c in selected_countries] if selected_countries else reference_bucket
        markets_extra = [m.lower() for m in st.session_state.additional_markets_data.keys()]
        markets = sorted(set(markets_base) | set(markets_extra))
        cols_per_row = 3
        num_rows = (len(markets) + cols_per_row - 1) // cols_per_row

        for row_idx in range(num_rows):
            cols = st.columns(cols_per_row)
            for col_idx, col in enumerate(cols):
                market_idx = row_idx * cols_per_row + col_idx
                if market_idx < len(markets):
                    market = markets[market_idx]
                    market_lower = market.lower()
                    # Always use data default as source of truth
                    data_default = default_ppp.get(market_lower, 1.0)
                    with col:
                        val = st.number_input(
                            label=f"{market.title()} PPP",
                            value=data_default,
                            step=0.000001,
                            format="%.6f",
                            key=f"ppp_input_{market_lower}_{st.session_state.ppp_version}",
                            help=f"Health PPP rate for {market.title()}",
                        )
                        # Store if different from default (use tolerance for float comparison)
                        if abs(val - data_default) > 0.0001:
                            st.session_state.custom_ppp_rates[market_lower] = val
                        elif market_lower in st.session_state.custom_ppp_rates:
                            del st.session_state.custom_ppp_rates[market_lower]

        # Reset button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Reset PPP to Defaults", key="reset_ppp_btn"):
                st.session_state.custom_ppp_rates = {}
                st.session_state.ppp_version += 1
                st.rerun()

    # Display assumptions panel
    if filter_options.get("assumptions"):
        st.markdown(
            """
        <div style='background: white;
                    padding: 1.5rem;
                    border-radius: 12px;
                    border: 1px solid #e2e8f0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
                    margin: 1rem 0;'>
            <h4 style='color: #1e293b; font-weight: 700; margin-top: 0;'>Assumptions & Sources</h4>
        """,
            unsafe_allow_html=True,
        )

        assumptions = filter_options["assumptions"]
        st.write(
            f"**Sources:** Pack prices from {assumptions['sources'].get('pack_prices', 'NURO')}; "
            f"PPP from {assumptions['sources'].get('ppp', 'OECD/WHO')}"
        )
        st.write(f"**PPP Rationale:** {assumptions['ppp_rationale']}")
        
        # Add MFN Formula Visualization
        st.markdown("**MFN Estimation (GENEROUS Model):**")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(
                "**MFN Price = 2nd Lowest PPP-Adjusted Price**\n\n"
                "1. Convert local currency prices to USD using exchange rates\n"
                "2. Adjust to PPP terms using health-specific purchasing power parities\n"
                "3. Select 2nd lowest value across ≥5 markets (GENEROUS reference basket)"
            )
        
        st.write(
            f"**Reference Basket (GENEROUS):** {', '.join(assumptions['reference_basket'])} — "
            f"minimum 5 markets required for valid MFN estimation"
        )

        st.markdown("</div>", unsafe_allow_html=True)

    # Custom Product Price Input Section
    with st.expander("Estimate MFN for Custom Product", expanded=False):
        st.markdown(
            "Enter local currency prices for your product across multiple markets to estimate MFN price using GENEROUS model (2nd lowest)."
        )

        col1, col2 = st.columns([1, 1])
        
        with col1:
            custom_product_name = st.text_input(
                "Product Name (optional)",
                placeholder="e.g., My Drug Product",
                key="custom_product_name"
            )

        with col2:
            st.markdown("")  # Spacing for alignment
            if st.button("View Assumptions", key="view_assumptions_custom"):
                st.info(
                    f"**Exchange Rates & PPP Rates:**\n\n"
                    f"Use the editable sections above (Exchange Rates and PPP Values) "
                    f"to override default values for sensitivity analysis."
                )

        st.markdown("**Enter Local Currency Prices by Market:**")
        
        # Create columns for input
        custom_prices = {}
        markets_base = [c.lower() for c in selected_countries] if selected_countries else [m.lower() for m in reference_bucket if m.lower() != "united states of america"]
        markets_extra = [m.lower() for m in st.session_state.additional_markets_data.keys() if m.lower() != "united states of america"]
        markets_for_custom = sorted(set(markets_base) | set(markets_extra))
        
        cols_per_row = 2
        num_rows = (len(markets_for_custom) + cols_per_row - 1) // cols_per_row

        for row_idx in range(num_rows):
            cols = st.columns(cols_per_row)
            for col_idx, col in enumerate(cols):
                market_idx = row_idx * cols_per_row + col_idx
                if market_idx < len(markets_for_custom):
                    market = markets_for_custom[market_idx]
                    with col:
                        price = st.number_input(
                            label=f"{market.title()} (Local Currency)",
                            value=0.0,
                            min_value=0.0,
                            step=0.01,
                            key=f"custom_price_{market}",
                            help=f"Enter local currency price for {market.title()}",
                        )
                        if price > 0:
                            custom_prices[market] = price

        # Estimate MFN button
        if custom_prices:
            if st.button("Estimate MFN Price", use_container_width=True, key="estimate_mfn_btn"):
                # Get exchange rates and PPP rates (use custom or defaults)
                try:
                    processed_data = load("processed_price_data")
                    ppp_data = load("ppp_2020_2023")
                    
                    exchange_rates = {}
                    ppp_rates = {}
                    
                    # Get defaults (use additional markets overrides where present)
                    if not processed_data.empty:
                        for market in custom_prices.keys():
                            default_ex = (
                                processed_data[processed_data["country"] == market]["exchange_rate"].iloc[0]
                                if not processed_data[processed_data["country"] == market].empty
                                else st.session_state.additional_markets_data.get(market.title(), {}).get("exchange_rate", 1.0)
                            )
                            exchange_rates[market] = st.session_state.custom_exchange_rates.get(market, default_ex)
                    
                    if not ppp_data.empty and "2023" in ppp_data.columns:
                        for market in custom_prices.keys():
                            default_ppp = (
                                ppp_data[ppp_data["country"] == market]["2023"].iloc[0]
                                if not ppp_data[ppp_data["country"] == market].empty
                                else st.session_state.additional_markets_data.get(market.title(), {}).get("ppp_rate", 1.0)
                            )
                            ppp_rates[market] = st.session_state.custom_ppp_rates.get(market, default_ppp)
                    
                    # Estimate MFN
                    result = estimate_mfn_custom_product(
                        market_prices=custom_prices,
                        exchange_rates=exchange_rates,
                        ppp_rates=ppp_rates,
                        gtn_map=st.session_state.custom_gtn_values if st.session_state.gtn_enabled else None,
                        apply_gtn=st.session_state.gtn_enabled,
                    )
                    
                    # Display results
                    st.success("MFN Estimation Complete")
                    
                    # Results table
                    results_data = []
                    for market in sorted(result["markets_used"]):
                        results_data.append({
                            "Market": market.title(),
                            "Local Price": f"{custom_prices[market]:.2f}",
                            "USD Price": f"{result['usd_prices'].get(market, 0):.2f}",
                            "PPP Price": f"{result['ppp_prices'].get(market, 0):.2f}",
                            "Net PPP Price": f"{result['net_prices'].get(market, '-'):.2f}" if st.session_state.gtn_enabled else "-",
                        })
                    
                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True, hide_index=True)
                    
                    # MFN Summary
                    st.markdown("---")
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.metric("Gross MFN Price (PPP)", f"${result['mfn_price']:.2f}" if result['mfn_price'] else "N/A")
                    
                    if st.session_state.gtn_enabled and result['net_mfn_price']:
                        with col2:
                            st.metric("Net MFN Price (PPP)", f"${result['net_mfn_price']:.2f}")
                    
                    st.info(
                        f"**GENEROUS Model:** MFN = 2nd lowest PPP price across {len(result['markets_used'])} markets\n\n"
                        f"**Markets Used:** {', '.join([m.title() for m in result['markets_used']])}"
                    )
                
                except Exception as e:
                    st.error(f"Failed to estimate MFN: {str(e)}")
        else:
            st.info("Enter at least one market price above to estimate MFN")

    # Export button and GTN toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        pass
    with col2:
        if st.button(
            "Export to Excel", use_container_width=True, disabled=not selected_brands
        ):
            if selected_brands:
                with st.spinner("Generating Excel file..."):
                    countries = (
                        selected_countries if selected_countries else None
                    )
                    packs = st.session_state.get("selected_packs", None)
                    # Pass custom GTN values if GTN enabled
                    gtn_values = st.session_state.custom_gtn_values if st.session_state.gtn_enabled else DEFAULT_GTN_BY_COUNTRY
                    # Filter WAC map to only relevant brands/packs
                    wac_filtered = {k: v for k, v in st.session_state.wac_prices.items() if k[0] in [b.lower() for b in selected_brands]}
                    excel_data, filename = export_to_excel(
                        selected_brands, countries, packs, st.session_state.gtn_enabled, gtn_values, wac_filtered if wac_filtered else None
                    )
                    if excel_data:
                        st.download_button(
                            label="Download",
                            data=excel_data,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                        st.success("Excel file ready!")

    # Additional filters for Pack (only show when brand is selected)
    if selected_brand:
        brand_filters = fetch_brand_specific_filters(selected_brand)

        st.markdown("<br>", unsafe_allow_html=True)

        # Get current selections from session state for persistence
        prev_selected_packs = st.session_state.get("selected_packs", [])

        available_packs = (
            fetch_packs_for_countries(selected_brand, selected_countries)
            if selected_countries
            else brand_filters.get("packs", [])
        )
        selected_packs = st.multiselect(
            label="Select Packs (optional)",
            options=available_packs,
            default=[p for p in prev_selected_packs if p in available_packs],
            placeholder="All packs",
            key="selected_packs",
        )

        # WAC Price Input Section
        with st.expander("Enter WAC Prices (optional)", expanded=False):
            st.markdown(
                "Enter Wholesale Acquisition Cost (WAC) per pack to compare against MFN prices."
            )

            # Build available packs to enter WAC for
            packs_for_wac = selected_packs if selected_packs else available_packs

            for pack in packs_for_wac:
                wac_key = (selected_brand.lower(), pack.lower())
                current_wac = st.session_state.wac_prices.get(wac_key, 0.0)

                wac_val = st.number_input(
                    label=f"WAC - {pack}",
                    value=current_wac,
                    min_value=0.0,
                    step=0.01,
                    key=f"wac_input_{pack}",
                    help=f"Enter WAC price for pack: {pack}",
                )

                if wac_val > 0:
                    st.session_state.wac_prices[wac_key] = wac_val
                elif wac_key in st.session_state.wac_prices:
                    del st.session_state.wac_prices[wac_key]

    else:
        selected_packs = None

    st.markdown("<br>", unsafe_allow_html=True)

    # Data display section
    if not selected_brand:
        st.markdown(
            """
        <div style='background: white;
                    padding: 4rem;
                    border-radius: 12px;
                    border: 1px solid #e2e8f0;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.04);
                    text-align: center;'>
            <h3 style='color: #64748b; font-weight: 600; margin-bottom: 0.5rem;'>No data to display</h3>
            <p style='color: #94a3b8; margin: 0;'>Please select a brand to view data</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Loading data..."):
            # Filter WAC map to only relevant brands/packs for display
            wac_display = {k: v for k, v in st.session_state.wac_prices.items() if k[0] in [b.lower() for b in selected_brands]}
            result = fetch_data(selected_brands, selected_countries, selected_packs, st.session_state.gtn_enabled, wac_display if wac_display else None)

            # Custom CSS for multi-level headers
            st.markdown(
                """
            <style>
                /* Year header styling */
                .dataframe thead tr:first-child th {
                    background: #ffffff !important;
                    color: white !important;
                    font-weight: 800 !important;
                    font-size: 14px !important;
                    border-right: 3px solid rgba(255,255,255,0.5) !important;
                    text-align: center !important;
                    padding: 12px 8px !important;
                }
                
                /* Metric header styling */
                .dataframe thead tr:last-child th {
                    background: #ffffff !important;
                    color: white !important;
                    font-weight: 700 !important;
                    font-size: 13px !important;
                    border-right: 2px solid rgba(255,255,255,0.3) !important;
                    padding: 12px 8px !important;
                }
            </style>
            """,
                unsafe_allow_html=True,
            )

            # Table 1: Cost Per Unit (Local) vs Cost Per Unit (USD)
            st.markdown(
                """
            <div style='background: white;
                        padding: 1.5rem 2rem;
                        border-radius: 12px 12px 0 0;
                        border: 1px solid #e2e8f0;
                        border-bottom: none;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.04);'>
                <h3 style='margin: 0; color: #1e293b; font-weight: 700; text-align: center;'>
                    Local Currency - USD Prices
                </h3>
            </div>
            """,
                unsafe_allow_html=True,
            )

            table1_df = create_display_table(result["table1"])

            if table1_df.empty:
                st.warning("No data available for Table 1")
            else:
                st.markdown(
                    """
                <div style='background: white;
                            padding: 0;
                            border-radius: 0 0 12px 12px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 4px 20px rgba(0,0,0,0.04);
                            overflow: hidden;
                            margin-bottom: 2rem;'>
                """,
                    unsafe_allow_html=True,
                )

                nrows = len(table1_df)
                if nrows > 10:
                    st.dataframe(
                        table1_df, use_container_width=True, height=400, hide_index=True
                    )
                else:
                    # Estimate row height (approx 35px per row + header)
                    row_height = 35
                    header_height = 40
                    height = header_height + row_height * (
                        nrows + 1 if nrows > 0 else 1
                    )
                    st.dataframe(
                        table1_df,
                        use_container_width=True,
                        height=height,
                        hide_index=True,
                    )

                st.markdown(
                    f"""
                <div style='text-align: center; 
                            padding: 1rem; 
                            color: #64748b; 
                            font-weight: 600;
                            background: #f8fafc;
                            border-top: 2px solid #e2e8f0;'>
                    Showing {nrows} rows
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Table 2: Cost Per Unit (USD) vs Cost Per Unit (PPP)
            st.markdown(
                """
            <div style='background: white;
                        padding: 1.5rem 2rem;
                        border-radius: 12px 12px 0 0;
                        border: 1px solid #e2e8f0;
                        border-bottom: none;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.04);'>
                <h3 style='margin: 0; color: #1e293b; font-weight: 700; text-align: center;'>
                    USD Prices - PPP Adjusted Prices
                </h3>
            </div>
            """,
                unsafe_allow_html=True,
            )

            table2_df = create_display_table(result["table2"])

            if table2_df.empty:
                st.warning("No data available for Table 2")
            else:
                st.markdown(
                    """
                <div style='background: white;
                            padding: 0;
                            border-radius: 0 0 12px 12px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 4px 20px rgba(0,0,0,0.04);
                            overflow: hidden;
                            margin-bottom: 2rem;'>
                """,
                    unsafe_allow_html=True,
                )

                nrows = len(table2_df)
                if nrows > 10:
                    st.dataframe(
                        table2_df, use_container_width=True, height=400, hide_index=True
                    )
                else:
                    row_height = 35
                    header_height = 40
                    height = header_height + row_height * (
                        nrows + 1 if nrows > 0 else 1
                    )
                    st.dataframe(
                        table2_df,
                        use_container_width=True,
                        height=height,
                        hide_index=True,
                    )

                st.markdown(
                    f"""
                <div style='text-align: center; 
                            padding: 1rem; 
                            color: #64748b; 
                            font-weight: 600;
                            background: #f8fafc;
                            border-top: 2px solid #e2e8f0;'>
                    Showing {nrows} rows
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Table 3: Cost Per Unit (USD) - MFN Price (USD)
            st.markdown(
                """
            <div style='background: white;
                        padding: 1.5rem 2rem;
                        border-radius: 12px 12px 0 0;
                        border: 1px solid #e2e8f0;
                        border-bottom: none;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.04);'>
                <h3 style='margin: 0; color: #1e293b; font-weight: 700; text-align: center;'>
                    US - MFN Price
                </h3>
            </div>
            """,
                unsafe_allow_html=True,
            )

            table3_df = create_display_table(result["table3"])

            if table3_df.empty:
                st.warning("No data available for Table 3")
            else:
                # Sort: fuller rows (with more valid data) first, emptier rows last
                # Count non-missing values in MFN Price columns for each row
                mfn_cols = [
                    col
                    for col in table3_df.columns
                    if isinstance(col, tuple) and col[1] == "MFN Price"
                ]

                def count_valid(row):
                    count = 0
                    for col in mfn_cols:
                        val = row[col]
                        if pd.notna(val) and val != "-" and val != "":
                            count += 1
                    return count

                table3_df = table3_df.copy()
                table3_df["_valid_mfn"] = table3_df.apply(count_valid, axis=1)
                # Sort descending by valid MFN count, then by pack name for stability
                table3_df = table3_df.sort_values(
                    ["_valid_mfn", ("", "Pack")], ascending=[False, True]
                ).drop(columns=["_valid_mfn"])

                st.markdown(
                    """
                <div style='background: white;
                            padding: 0;
                            border-radius: 0 0 12px 12px;
                            border: 1px solid #e2e8f0;
                            box-shadow: 0 4px 20px rgba(0,0,0,0.04);
                            overflow: hidden;'>
                """,
                    unsafe_allow_html=True,
                )

                nrows = len(table3_df)
                if nrows > 10:
                    st.dataframe(
                        table3_df, use_container_width=True, height=400, hide_index=True
                    )
                else:
                    row_height = 35
                    header_height = 40
                    height = header_height + row_height * (
                        nrows + 1 if nrows > 0 else 1
                    )
                    st.dataframe(
                        table3_df,
                        use_container_width=True,
                        height=height,
                        hide_index=True,
                    )

                st.markdown(
                    f"""
                <div style='text-align: center; 
                            padding: 1rem; 
                            color: #64748b; 
                            font-weight: 600;
                            background: #f8fafc;
                            border-top: 2px solid #e2e8f0;'>
                    Showing {nrows} rows
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
