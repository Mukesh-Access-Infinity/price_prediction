import streamlit as st
import pandas as pd
import io
from datetime import datetime
from utils import get_processed_data, unroll_agg
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


# Load data once at startup
@st.cache_data
def get_data():
    """Load data from get_processed_data"""
    return get_processed_data(refresh=False)


@st.cache_data
def fetch_filter_options():
    """Get available filter options from data"""
    try:
        data = get_data()
        brands = sorted(set([item["Brand Name"] for item in data]))
        return {"brands": brands}
    except Exception as e:
        st.error(f"Failed to fetch filter options: {str(e)}")
        return {"brands": []}


def fetch_data(brand: Optional[str] = None):
    """Fetch and filter data for a specific brand"""
    try:
        all_data = get_data()

        if not brand:
            return {
                "table1": pd.DataFrame(),
                "table2": pd.DataFrame(),
                "table3": pd.DataFrame(),
            }

        # Filter data for selected brand
        brand_data = [item for item in all_data if item["Brand Name"] == brand]

        if not brand_data:
            return {
                "table1": pd.DataFrame(),
                "table2": pd.DataFrame(),
                "table3": pd.DataFrame(),
            }

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

        for item in brand_data:
            country = item["Country"]
            pack = item["Pack"]
            year_data = item["Year"]

            # Prepare row for table 1
            row1 = {"Country": country, "Pack": pack}
            # Prepare row for table 2
            row2 = {"Country": country, "Pack": pack}
            # Prepare row for table 3
            row3 = {"Country": country, "Pack": pack}

            for year in all_years:
                metrics = year_data.get(year, {})
                # Table 1 columns
                if country.lower() != "united states of america":
                    row1[(year, "Local Price")] = metrics.get(
                        "Cost Per Unit Local", None
                    )
                    row1[(year, "USD Price")] = metrics.get("Cost Per Unit USD", None)

                    # Table 2 columns
                    row2[(year, "USD Price")] = metrics.get("Cost Per Unit USD", None)
                    row2[(year, "PPP Adjusted Price")] = metrics.get(
                        "Cost Per Unit PPP", None
                    )
                else:
                    # Table 3 columns
                    row3[(year, "USD Price")] = metrics.get("Cost Per Unit USD", None)
                    row3[(year, "MFN Price")] = metrics.get("MFN Price USD", None)
            if country.lower() != "united states of america":
                table1_rows.append(row1)
                table2_rows.append(row2)
            else:
                table3_rows.append(row3)

        # Create DataFrames with multi-index columns
        df1 = pd.DataFrame(table1_rows)
        df2 = pd.DataFrame(table2_rows)
        df3 = pd.DataFrame(table3_rows)

        # Separate basic columns from year columns
        basic_cols = ["Country", "Pack"]

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


def export_to_excel(brand):
    """Generate Excel export"""
    try:
        result = fetch_data(brand=brand)

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
                df3.to_excel(writer, index=False, sheet_name="US - MFN")

        output.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return output.getvalue(), f"price_data_{brand}_{timestamp}.xlsx"
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
            Brand Prediction Dashboard
        </h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Fetch filter options
    filter_options = fetch_filter_options()

    with st.container():
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(
                """
            <h3 style='margin: 0 0 1rem 0; color: #1e293b; font-weight: 700;'>Select Brand</h3>
            """,
                unsafe_allow_html=True,
            )

            # Single select dropdown for brand
            selected_brand = st.selectbox(
                label="Choose a brand to view data",
                options=[""] + filter_options.get("brands", []),
                index=0,
                placeholder="Select a brand...",
                label_visibility="collapsed",
                key="selected_brand",
            )

        with col2:
            st.markdown(
                """
            <br>
            <br>
            <br>
            """,
                unsafe_allow_html=True,
            )
            if st.button("Export to Excel", use_container_width=True, disabled=not selected_brand):
                if selected_brand:
                    with st.spinner("Generating Excel file..."):
                        excel_data, filename = export_to_excel(selected_brand)
                        if excel_data:
                            st.download_button(
                                label="Download File",
                                data=excel_data,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                            )
                            st.success("Excel file ready for download!")

    st.markdown("</div>", unsafe_allow_html=True)
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
            result = fetch_data(selected_brand)

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

                st.dataframe(
                    table1_df, use_container_width=True, height=400, hide_index=True
                )

                st.markdown(
                    f"""
                <div style='text-align: center; 
                            padding: 1rem; 
                            color: #64748b; 
                            font-weight: 600;
                            background: #f8fafc;
                            border-top: 2px solid #e2e8f0;'>
                    Showing {len(table1_df)} rows
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

                st.dataframe(
                    table2_df,
                    use_container_width=True,
                    height=400,
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
                    Showing {len(table2_df)} rows
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

                st.dataframe(
                    table3_df,
                    use_container_width=True,
                    height=400,
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
                    Showing {len(table3_df)} rows
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
