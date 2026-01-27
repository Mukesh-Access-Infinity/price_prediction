import json
import bs4
import requests
import os

DIR = "./data/policy/"
link_map = {
    "amcp": "https://www.amcp.org/sites/default/files/2025-12/fed_update_12_19_mfn_announcements.pdf",
    "phrma": "https://phrma.org/resources/phrma-statement-on-december-cms-december-cms-guard-and-globe-proposed-rules",
    "fda": "https://www.thefdalawblog.com/2026/01/mfn-drug-pricing-update-after-generous-guard-and-globe-issue-from-cmss-innovation-center-part-i/",
    # "lexology": "https://www.lexology.com/library/detail.aspx?g=fdc8604b-a365-486d-9072-37211a410aca",
    "lexology": "https://www.hoganlovells.com/en/publications/cms-issues-mandatory-medicare-models-implementing-most-favored-nation-drug-pricing",
    "goodwindlaw": "https://www.goodwinlaw.com/en/insights/publications/2025/12/alerts-lifesciences-cms-releases-mfn-drug-pricing-models",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def get_link(s: str):
    if s in link_map:
        return link_map[s]
    raise ValueError(f"No link found for key: {s}")


def _scrape_amcp():
    path = DIR + "amcp.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing_text = f.read()
            if existing_text:
                return path


def _scrape_fda():
    path = DIR + "fda.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing_text = f.read()
            if existing_text:
                return path
    url = get_link("fda")
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.content, "html.parser")
    h1_texts = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    content_blocks = soup.find_all(class_="colorized narrative")

    content_texts = []
    for block in content_blocks:
        text = block.get_text(separator=" ", strip=True)
        if text:
            content_texts.append(text)

    full_text = "\n\n".join(h1_texts + content_texts)
    path = DIR + "fda.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(full_text)
    return path


def _scrape_goodwindlaw():
    path = DIR + "goodwindlaw.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing_text = f.read()
            if existing_text:
                return path
    url = get_link("goodwindlaw")
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.content, "html.parser")
    h1_texts = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    content_blocks = soup.find_all(
        class_="BasicContentRichTextWithFlexibleContentCard_TwoColumnContentPadded__E61a6"
    )

    content_texts = []
    for block in content_blocks:
        # separator preserves spacing between elements
        text = block.get_text(separator=" ", strip=True)
        if text:
            content_texts.append(text)

    full_text = "\n\n".join(h1_texts + content_texts)
    with open(path, "w", encoding="utf-8") as f:
        f.write(full_text)
    return path


from playwright.sync_api import sync_playwright
import bs4
import os


def fetch_html_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        html = page.content()
        browser.close()
        return html


def _scrape_phrma():
    path = DIR + "phrma.txt"

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            if f.read().strip():
                return path

    url = get_link("phrma")
    html = fetch_html_playwright(url)

    soup = bs4.BeautifulSoup(html, "html.parser")
    h1_texts = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]

    text = "\n".join(h1_texts) + "\n\n" + "\n\n".join(paragraphs)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return path


def _scrape_lexology():
    path = DIR + "lexology.txt"

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            if f.read().strip():
                return path

    url = get_link("lexology")
    html = fetch_html_playwright(url)

    soup = bs4.BeautifulSoup(html, "html.parser")
    h1_texts = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    content_blocks = soup.find_all(class_="container")

    content_texts = []
    for block in content_blocks:
        text = block.get_text(separator=" ", strip=True)
        if text:
            content_texts.append(text)

    full_text = "\n\n".join(h1_texts + content_texts)

    with open(path, "w", encoding="utf-8") as f:
        f.write(full_text)

    return path


def _scrape_all():
    func = []
    func.append(_scrape_phrma)
    func.append(_scrape_fda)
    func.append(_scrape_lexology)
    func.append(_scrape_goodwindlaw)
    func.append(_scrape_amcp)
    res: list[str] = []
    for f in func:
        try:
            res.append(f())
        except Exception as e:
            print(f"Error scraping {f.__name__}: {e}")
    return res


from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class PolicyAnalysis(BaseModel):
    policy_name: str = Field(..., description="Official name of the policy or program")

    effective_date: Optional[date] = Field(
        None, description="Date the policy takes effect"
    )

    duration: Optional[str] = Field(
        None,
        description="Duration of the policy (e.g., fixed term, indefinite, pilot period)",
    )

    proposal_date: Optional[date] = Field(
        None, description="Date the policy was proposed or announced"
    )

    policy_structure: List[str] = Field(
        ...,
        description=(
            "Brief overview of policy or program structure. "
            "Each list item should be a bullet point. "
            "Target length ~100 words total."
        ),
    )

    drug_eligibility_criteria: str = Field(
        ...,
        description="Detailed description of drug eligibility criteria (~200 words)",
    )

    international_pricing_benchmark: str = Field(
        ...,
        description="Explanation of international pricing benchmark methodology (~200 words)",
    )

    benchmark_comparison: str = Field(
        ...,
        description="Comparison of benchmark prices across reference countries (~200 words)",
    )

    enforcement_and_penalties: str = Field(
        ...,
        description="Enforcement mechanisms and penalties for non-compliance (~150 words)",
    )

    what_you_need_to_know: List[str] = Field(
        ...,
        description=(
            "Key takeaways for stakeholders. "
            "Each list item should be a bullet point. "
            "Target length 150–200 words total."
        ),
    )

    implications_for_pharma_companies: List[str] = Field(
        ...,
        description=(
            "Implications for pharmaceutical companies. "
            "Each list item should be a bullet point. "
            "Target length ~200 words total."
        ),
    )
    model_config = {"extra": "ignore"}

import os
from datetime import date
from typing import List, Optional
import streamlit as st
from pydantic import BaseModel, Field
from ai import call_llm
from google.genai.types import Part
from pathlib import Path

DIR = Path("./data/policy/")
DIR.mkdir(parents=True, exist_ok=True)

TEXT_FILES = {
    "phrma": DIR / "phrma.txt",
    "fda": DIR / "fda.txt",
    "lexology": DIR / "lexology.txt",
    "goodwindlaw": DIR / "goodwindlaw.txt",
    "amcp": DIR / "amcp.txt",
}


# ---- Load Text Files Safely ----
def load_policy_texts() -> List[Part]:
    parts = []
    for name, path in TEXT_FILES.items():
        if not path.exists():
            st.warning(f"Text file for {name} not found: {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                parts.append(Part.from_text(text=text))
            else:
                st.warning(f"Text file for {name} is empty: {path}")
        except Exception as e:
            st.error(f"Failed to read {name}: {e}")
    return parts


# ---- Load or Call LLM ----
@st.cache_data(show_spinner=True)
def get_policy_analysis(parts: List[Part]) -> dict:
    if not parts:
        raise ValueError("No policy content available to analyze.")
    prompt = (
        "You are an expert policy analyst. Given the content of various policy documents, "
        "extract and summarize the key details into a structured format."
    )
    response = call_llm(prompt=prompt, contents=parts, response_schema=PolicyAnalysis)
    r = PolicyAnalysis.model_validate(response)
    return r.model_dump()


# ---- Streamlit UI ----
st.set_page_config(page_title="Policy Analysis", layout="wide")

parts = load_policy_texts()
if not parts:
    st.error("No policy documents loaded. Please ensure scraping has run successfully.")
    st.stop()

try:
    pa = PolicyAnalysis.model_validate(get_policy_analysis(parts))
except Exception as e:
    st.error(f"Failed to generate policy analysis: {e}")
    st.stop()

# ---- Display ----
st.title(pa.policy_name)
st.divider()
with st.expander("View Sources"):
    for name, url in link_map.items():
        # Only show sources that are not None
        if url and url != ...:
            st.markdown(f"- {url}")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        "Effective Date",
        (
            pa.effective_date.strftime("%Y-%m-%d")
            if pa.effective_date
            else "Not specified"
        ),
    )
with col2:
    st.metric(
        "Proposal Date",
        pa.proposal_date.strftime("%Y-%m-%d") if pa.proposal_date else "Not specified",
    )
with col3:
    st.metric("Duration", pa.duration or "Not specified")

st.divider()

st.header("Policy Structure")
for item in pa.policy_structure:
    st.markdown(f"- {item}")

st.divider()

st.header("Drug Eligibility Criteria")
st.write(pa.drug_eligibility_criteria)

st.divider()

st.header("International Pricing Benchmark")
st.write(pa.international_pricing_benchmark)

st.divider()

st.header("Benchmark Comparison")
st.write(pa.benchmark_comparison)

st.divider()

st.header("Enforcement and Penalties")
st.write(pa.enforcement_and_penalties)

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.header("What You Need to Know")
    for item in pa.what_you_need_to_know:
        st.markdown(f"- {item}")

with col_right:
    st.header("Implications for Pharma Companies")
    for item in pa.implications_for_pharma_companies:
        st.markdown(f"- {item}")
