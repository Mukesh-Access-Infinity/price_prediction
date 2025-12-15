import os
import pandas as pd

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
    data = data.rename(
        columns=lambda c: (
            f"{c.split('-', 1)[1]}-{c.split('-', 1)[0]}"
            if c[:4].isdigit() and "-" in c
            else c
        )
    )
    id_cols = ["brand_name", "country", "form", "formulation", "price_id"]
    long_df = (
        pd.wide_to_long(
            data,
            stubnames=[
                "price",
                "exchange_rate",
                "target_currency",
                "cost_per_unit",
                "cost_per_strength_unit",
            ],
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
            & df["country"].isin(ppp_["country"].unique())
        ]
        df = df.merge(ppp_, on=["country", "year"], how="left")
        df.drop_duplicates(inplace=True, subset=UNIQUE_COLS)
        df.dropna(subset=["usd_price_per_unit"], inplace=True)
        df["usd_price"] = df["price"] * df["exchange_rate"]
        df["ppp_price_per_unit"] = df["cost_per_unit"] / df["ppp_rate"]
        df["ppp_price"] = df["price"] / df["ppp_rate"]
        df.drop(columns=["ppp_rate"], inplace=True)
        df["mfn_price"] = df.groupby(["year", "brand_name", "form"])[
            "ppp_price"
        ].transform(lambda x: x.nsmallest(2).max())
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
