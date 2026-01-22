import os
import pandas as pd


reference_bucket = [
    "United Kingdom",
    "France",
    "Germany",
    "Italy",
    "Canada",
    "Japan",
    "Denmark",
    "Switzerland",
    "United States of America",
]

# Default gross-to-net (GTN) assumptions by market (fractions)
DEFAULT_GTN_BY_COUNTRY = {
    "united kingdom": 0.40,
    "france": 0.35,
    "germany": 0.25,
    "italy": 0.50,
    "canada": 0.40,
    "japan": 0.20,
    "denmark": 0.25,
    "switzerland": 0.25,
}

PPP_RATIONALE = (
    "Prices were adjusted using OECD health-specific purchasing power parities to "
    "reflect differences in healthcare input costs across countries. Health PPPs were "
    "selected as the base case to avoid distortion from non-health consumption baskets. "
    "GDP PPP was explored in sensitivity analyses."
)

# Brief explanation on how net prices are calculated from GTN
NET_PRICE_EXPLANATION = (
    "Net prices represent estimated post-discount prices after applying "
    "standard country-specific gross-to-net (GTN) adjustments."
    "The resulting net price indicates the expected realized price level."
)

# Brief explanation on how WAC differentials are calculated
WAC_DIFFERENTIAL_EXPLANATION = (
    "WAC differentials indicate the percentage difference between the estimated "
    "U.S. MFN price and the Wholesale Acquisition Cost (WAC) provided by the user. "
    "This comparison highlights whether the MFN price is above or below WAC."
)

data_root = "./data"
os.makedirs(data_root, exist_ok=True)


def save(df: pd.DataFrame, table_name: str):
    df.to_pickle(f"./{data_root}/{table_name}.pickle")


def load(
    table_name: str,
) -> pd.DataFrame:
    if os.path.exists(f"./{data_root}/{table_name}.pickle"):
        return pd.read_pickle(f"./{data_root}/{table_name}.pickle")
    return pd.DataFrame()


import re
from collections import defaultdict
from typing import Iterable, Dict, Any
import pandas as pd

BASE_COLS = (
    "brand_name",
    "country",
    "form",
    "formulation",
    "price_id",
)

METRIC_COLS = (
    "price",
    "exchange_rate",
    "target_currency",
    "cost_per_unit",
    "cost_per_strength_unit",
)


def compute_second_lowest(values: pd.Series) -> float:
    """
    Return the second-lowest value; if fewer than two entries, return the min.
    This is the GENEROUS model formula for MFN pricing.
    """
    clean = values.dropna()
    if clean.empty:
        return float("nan")
    if len(clean) == 1:
        return float(clean.min())
    return float(clean.nsmallest(2).max())


def estimate_mfn_custom_product(
    market_prices: Dict[str, float],
    exchange_rates: Dict[str, float],
    ppp_rates: Dict[str, float],
    gtn_map: Dict[str, float] = None,
    apply_gtn: bool = False,
) -> Dict[str, Any]:
    """
    Estimate MFN price for a custom product using GENEROUS model (second-lowest PPP).
    
    Args:
        market_prices: Dict of {country: local_currency_price}
        exchange_rates: Dict of {country: exchange_rate_to_usd}
        ppp_rates: Dict of {country: ppp_rate}
        gtn_map: Dict of {country: gtn_fraction} for gross-to-net conversion
        apply_gtn: Whether to apply GTN conversion
    
    Returns:
        Dict with:
        - usd_prices: {country: usd_price}
        - ppp_prices: {country: ppp_price}
        - net_prices: {country: net_ppp_price} (if apply_gtn)
        - mfn_price: second_lowest_ppp_price
        - net_mfn_price: second_lowest_net_ppp_price (if apply_gtn)
        - markets_used: list of countries with valid data
    """
    if gtn_map is None:
        gtn_map = {}
    
    result = {
        "usd_prices": {},
        "ppp_prices": {},
        "net_prices": {},
        "markets_used": [],
    }
    
    # Calculate USD and PPP prices
    for country, local_price in market_prices.items():
        country_lower = country.lower()
        
        if country_lower not in exchange_rates or country_lower not in ppp_rates:
            continue
        
        ex_rate = exchange_rates[country_lower]
        ppp_rate = ppp_rates[country_lower]
        
        if ex_rate <= 0 or ppp_rate <= 0:
            continue
        
        usd_price = local_price * ex_rate
        ppp_price = local_price / ppp_rate
        
        result["usd_prices"][country] = usd_price
        result["ppp_prices"][country] = ppp_price
        result["markets_used"].append(country)
        
        # Apply GTN if enabled
        if apply_gtn and country_lower in gtn_map:
            gtn_factor = 1.0 - gtn_map[country_lower]
            net_price = ppp_price * gtn_factor
            result["net_prices"][country] = net_price
    
    # Calculate MFN as second-lowest PPP price
    if len(result["ppp_prices"]) >= 1:
        ppp_values = list(result["ppp_prices"].values())
        if len(ppp_values) >= 2:
            result["mfn_price"] = sorted(ppp_values)[1]
        else:
            result["mfn_price"] = min(ppp_values)
    else:
        result["mfn_price"] = None
    
    # Calculate net MFN if GTN applied
    if apply_gtn and len(result["net_prices"]) >= 1:
        net_values = list(result["net_prices"].values())
        if len(net_values) >= 2:
            result["net_mfn_price"] = sorted(net_values)[1]
        else:
            result["net_mfn_price"] = min(net_values)
    else:
        result["net_mfn_price"] = None
    
    return result


def apply_gtn(df: pd.DataFrame, gtn_map: dict) -> pd.DataFrame:
    """
    Apply country-level GTN rates to derive net prices and recompute MFN on net PPP.

    Adds columns:
    - net_cost_per_unit
    - net_usd_price_per_unit
    - net_ppp_price_per_unit
    - net_ppp_price
    - net_mfn_price
    """

    if df.empty:
        return df

    gtn_series = df["country"].str.lower().map(gtn_map).fillna(0.0)
    factor = 1.0 - gtn_series

    result = df.copy()

    if "cost_per_unit" in result:
        result["net_cost_per_unit"] = result["cost_per_unit"] * factor

    if "usd_price_per_unit" in result:
        result["net_usd_price_per_unit"] = result["usd_price_per_unit"] * factor

    if "ppp_price_per_unit" in result:
        result["net_ppp_price_per_unit"] = result["ppp_price_per_unit"] * factor

    if "ppp_price" in result:
        result["net_ppp_price"] = result["ppp_price"] * factor

    # Recompute MFN using net PPP price
    if "net_ppp_price" in result:
        result["net_mfn_price"] = (
            result.groupby(["year", "brand_name"])["net_ppp_price"]
            .transform(compute_second_lowest)
        )

    return result


def validate_df(
    df: pd.DataFrame,
    *,
    base_columns: Iterable[str] = BASE_COLS,
    allowed_metrics: Iterable[str] = METRIC_COLS,
) -> Dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    year_col_pattern = re.compile(r"^(?P<year>\d{4})-(?P<metric>.+)$")

    base_columns = set(base_columns)
    allowed_metrics = set(allowed_metrics)

    errors = {
        "unknown_columns": [],
        "malformed_columns": [],
        "invalid_years": [],
        "invalid_metrics": [],
        "missing_metrics_by_year": {},
    }

    seen_by_year = defaultdict(set)
    observed_years = set()

    for col in df.columns:
        # base columns
        if col in base_columns:
            continue

        match = year_col_pattern.match(col)
        if not match:
            errors["malformed_columns"].append(col)
            continue

        year = int(match.group("year"))
        metric = match.group("metric")

        if metric not in allowed_metrics:
            errors["invalid_metrics"].append(col)
            continue

        observed_years.add(year)
        seen_by_year[year].add(metric)

    years_to_check = sorted(observed_years)

    for year in years_to_check:
        missing = allowed_metrics - seen_by_year.get(year, set())
        if missing:
            errors["missing_metrics_by_year"][year] = sorted(missing)

    errors = {k: v for k, v in errors.items() if v}

    return errors


def load_or_build_long_table():
    df = load("long_data_table")
    if not df.empty:
        return df
    file = f"./{data_root}/data.xlsx"
    df_path = f"./{data_root}/data.pickle"
    if os.path.exists(df_path):
        data = pd.read_pickle(df_path)
    else:
        data = pd.read_excel(file)
        data.to_pickle(df_path)
    data.columns = data.columns.str.lower()
    errors = validate_df(df)
    if errors:
        _ = ""
        for k, v in errors.items():
            _ += f"{k.replace('_',' ').title()}: {v}\n"
        return _
    data = data.rename(
        columns=lambda c: (
            f"{c.split('-', 1)[1]}-{c.split('-', 1)[0]}"
            if c[:4].isdigit() and "-" in c
            else c
        )
    )
    id_cols = list(BASE_COLS)
    long_df = (
        pd.wide_to_long(
            data,
            stubnames=list(METRIC_COLS),
            i=id_cols,
            j="year",
            sep="-",
            suffix=r"\d{4}",
        )
        .reset_index()
        .sort_values(["brand_name", "year"])
    )
    save(long_df, "long_data_table")
    return long_df


def get_agg(df: pd.DataFrame):
    result = []
    for (brand, country, pack), g in df.groupby(
        ["brand_name", "country", "form"], sort=False
    ):
        year_dict = {}
        for _, row in g.iterrows():
            year_dict[row["year"]] = {
                "Cost Per Unit Local": row["cost_per_unit"],
                "Cost Per Unit USD": row["usd_price_per_unit"],
                "Cost Per Unit PPP": row["ppp_price_per_unit"],
                "MFN Price USD": row["mfn_price"],
            }
        result.append(
            {
                "Brand Name": brand,
                "Country": country.title(),
                "Pack": pack,
                "Year": year_dict,
            }
        )
    return result


def unroll_agg(agg):
    rows = []
    for rec in agg:
        for year, values in rec["Year"].items():
            rows.append(
                {
                    "brand_name": rec["Brand Name"],
                    "country": rec["Country"],
                    "form": rec["Pack"],
                    "year": year,
                    "cost_per_unit": values["Cost Per Unit Local"],
                    "usd_price_per_unit": values["Cost Per Unit USD"],
                    "ppp_price_per_unit": values["Cost Per Unit PPP"],
                    "mfn_price": values["MFN Price USD"],
                }
            )
    return pd.DataFrame(rows)


def get_processed_data(refresh=False):
    def _():
        file = f"./{data_root}/data.xlsx"
        df_path = f"./{data_root}/data.pickle"
        df = load_or_build_long_table()
        if isinstance(df, str):
            return str
        df.drop(columns=["price_id", "formulation"], inplace=True, errors="ignore")
        ppp_2020_2023 = f"./{data_root}/ppp_2020_2023.xlsx"
        ppp_2020_2023_data = pd.read_excel(ppp_2020_2023)
        ppp_2020_2023_data["country"] = ppp_2020_2023_data["country"].str.lower()
        save(ppp_2020_2023_data, "ppp_2020_2023")
        ppp = load("ppp_2020_2023")
        UNIQUE_COLS = ["brand_name", "country", "form", "year"]
        PRICE_COLS = [
            "price",
            "exchange_rate",
            "cost_per_unit",
            "cost_per_strength_unit",
        ]
        df = df.dropna(
            subset=PRICE_COLS,
            how="all",
        )
        df["country"] = df["country"].str.lower()
        df = df[df["country"].isin([i for i in {_.lower() for _ in reference_bucket}])]
        brand_year_country_count = df.groupby(["brand_name", "year"])[
            "country"
        ].nunique()
        bad_brand_years = brand_year_country_count[brand_year_country_count < 5].index
        bad_brand_years
        df = df[~df.set_index(["brand_name", "year"]).index.isin(bad_brand_years)]
        df.loc[df["target_currency"] == "GBP", "exchange_rate"] = 1.0
        df[df["exchange_rate"].isna()][["country", "year"]].drop_duplicates()[
            "year"
        ].value_counts().sort_index()
        need_exchange_rate_EUR_countries = ["france", "belgium"]
        need_exchange_rate_EUR_countries = ["france", "belgium"]
        germany_rates = df[df["country"] == "germany"][["year", "exchange_rate"]]
        df = df.merge(germany_rates, on="year", how="left", suffixes=("", "_germany"))
        mask = (
            df["country"].isin(need_exchange_rate_EUR_countries)
            & df["exchange_rate"].isna()
        )
        df.loc[mask, "exchange_rate"] = df.loc[mask, "exchange_rate_germany"]
        df.loc[
            df["target_currency"].isna() & df["country"].isin(["france", "belgium"]),
            "target_currency",
        ] = "USD"
        df = df.drop(columns=["exchange_rate_germany"])
        df["usd_price_per_unit"] = df["cost_per_unit"] * df["exchange_rate"]
        ppp_ = ppp.melt(id_vars="country", var_name="year", value_name="ppp_rate")
        ppp_["year"] = ppp_["year"].astype(int)
        df = df[
            df["year"].isin(ppp_["year"].unique())
            & df["country"].isin([i for i in {_.lower() for _ in reference_bucket}])
        ]
        df = df.merge(ppp_, on=["country", "year"], how="left")
        df.drop_duplicates(inplace=True, subset=UNIQUE_COLS)
        df.dropna(subset=["usd_price_per_unit"], inplace=True)
        df["usd_price"] = df["price"] * df["exchange_rate"]
        df["ppp_price_per_unit"] = df["cost_per_unit"] / df["ppp_rate"]
        df["ppp_price"] = df["price"] / df["ppp_rate"]
        df.drop(columns=["ppp_rate"], inplace=True)
        df["mfn_price"] = df.groupby(["year", "brand_name"])["ppp_price"].transform(
            lambda x: x.nsmallest(2).max()
        )
        df = df.reset_index(drop=True)
        save(df, "processed_price_data")
        return get_agg(df)

    if not refresh:
        try:
            df = load("processed_price_data")
            if df.empty:
                return _()
            return get_agg(df)
        except Exception:
            return _()
    else:
        return _()
