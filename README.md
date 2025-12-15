# Price Prediction Dashboard

This repository contains a small Streamlit-based dashboard for inspecting processed price data and exporting it to Excel. The main components are:

- `app.py`: Streamlit application that provides a UI to select a brand and view two tables comparing local currency, USD, and PPP adjusted prices. It also supports exporting the displayed tables to an Excel file.
- `utils.py`: Data loading and processing utilities. Functions read an Excel source (under `data/`), transform it to a "long" format, merge PPP and exchange rate information, and prepare aggregated records used by the Streamlit UI.
- `data/`: Expected location for input files used by `utils.py` (for example `data.xlsx`, `ppp_2020_2023.xlsx`). Processed data is stored as pickles in this folder.

## Requirements

Python 3.9+ recommended. Install dependencies from `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

If you prefer a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Expected data files

Place your source data files inside the `data` folder. The app and utilities expect at least the following files (names referenced in `utils.py`):

- `data/data.xlsx` — main dataset exported from your source (expected to have columns that include year-suffixed fields like `price-2020`, `exchange_rate-2020`, etc.).
- `data/ppp_2020_2023.xlsx` — PPP rates table containing a `country` column and year columns `2020, 2021, 2022, 2023`.

When `utils.get_processed_data()` runs it will create and use pickled copies inside `data/` to speed up subsequent loads (files like `data.pickle`, `long_data_table.pickle`, `processed_price_data.pickle`, etc.).

## Run the Streamlit app

From the repository root run:

```powershell
streamlit run app.py
```

On Windows PowerShell, you may need to unblock scripts or use the provided `start.ps1` helper. The app will open in your browser at `http://localhost:8501` by default.

## Main features

- Brand selector: choose a brand to inspect its price data across countries and packs.
- Table 1: Cost per unit in local currency and USD (year-wise).
- Table 2: Cost per unit in USD and PPP-adjusted values (year-wise).
- Export to Excel: generate an `.xlsx` containing both tables for the selected brand.

## Useful functions in `utils.py`

- `load_or_build_long_table()` — reads `data/data.xlsx` and converts wide-year columns into long format. Saves a pickled `long_data_table` for later use.
- `get_processed_data(refresh=False)` — builds processed price data, merges PPP values, computes USD and PPP prices, and saves `processed_price_data` as a pickle. Returns an aggregated list-of-dicts used by the Streamlit UI. If `refresh=True` the function forces rebuilding.
- `get_agg(df)` / `unroll_agg(agg)` — helpers for aggregating processed data into the format expected by the UI and reversing that aggregation.

## Troubleshooting

- Missing data files: If `data/data.xlsx` or `data/ppp_2020_2023.xlsx` are not present, `utils` will raise errors when processing. Add the expected files to `data/` and re-run.
- Permissions: On Windows, PowerShell execution policies can block scripts. Use `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` if you need to run `start.ps1`.
- Pandas/Excel errors: Ensure `openpyxl` or required Excel engine is installed (check `requirements.txt`).
- Database references: `utils.py` contains commented-out PostgreSQL connection strings but the app uses pickled files in `data/` by default — you do not need PostgreSQL to run the app.

Generated README for the Price Prediction Dashboard.
