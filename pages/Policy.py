import json
import bs4
import pydantic
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
    # -----------------------------------------------Different response type LLM -----
    "cms": [
        "https://www.cms.gov/newsroom/press-releases/cms-announces-new-drug-payment-model-strengthen-medicaid-better-serve-vulnerable-americans",
        "https://www.cms.gov/newsroom/press-releases/cms-announces-selection-drugs-third-cycle-medicare-drug-price-negotiation-program-including-first",
    ],
    "aifa": "https://www.aifa.gov.it/en/-/applicazione-riduzione-5-aggiornamento-prezzi-al-pubblico",
    "simon_kucher": "https://www.simon-kucher.com/en/insights/what-2026-lfss-and-2024-ceps-activity-report-signal-frances-pma",
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

from pathlib import Path

def _ret(path: str|Path):
    if Path(path).is_file() or os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            existing_text = f.read().strip()
            if existing_text:
                return existing_text
            return None
    os.makedirs(os.path.dirname(path), exist_ok=True)


def get_link(s: str):
    if s in link_map:
        return link_map[s]
    raise ValueError(f"No link found for key: {s}")


def _scrape_cms():
    path = DIR / "cms.txt"
    d = _ret(path)
    if d:
        return d
    return "ignore"


def _scrape_amcp():
    path = DIR / "amcp.txt"
    d = _ret(path)
    if d:
        return d
    return "ignore"


def _scrape_fda():
    path = DIR / "fda.txt"
    d = _ret(path)
    if d:
        return d
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
    path = DIR / "fda.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(full_text)
    return full_text


def _scrape_goodwindlaw():
    path = DIR / "goodwindlaw.txt"
    d = _ret(path)
    if d:
        return d
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
    return full_text


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
    path = DIR / "phrma.txt"

    d = _ret(path)
    if d:
        return d

    url = get_link("phrma")
    html = fetch_html_playwright(url)

    soup = bs4.BeautifulSoup(html, "html.parser")
    h1_texts = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]

    text = "\n".join(h1_texts) + "\n\n" + "\n\n".join(paragraphs)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return text


def _scrape_lexology():
    path = DIR / "lexology.txt"
    d = _ret(path)
    if d:
        return d

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

    return full_text


def _scrape_simon_kucher():
    path = DIR / "simon_kucher.txt"
    d = _ret(path)
    if d:
        return d
    return "ignore"


def _scrape_aifa():
    path = DIR / "aifa.txt"
    d = _ret(path)
    if d:
        return d
    return "ignore"


def _scrape_all():
    func = []
    func.append(("phrma", _scrape_phrma))
    func.append(("fda", _scrape_fda))
    func.append(("lexology", _scrape_lexology))
    func.append(("goodwindlaw", _scrape_goodwindlaw))
    func.append(("amcp", _scrape_amcp))
    func.append(("cms", _scrape_cms))
    func.append(("simon_kucher", _scrape_simon_kucher))
    func.append(("aifa", _scrape_aifa))
    res: list[tuple[str, str]] = []
    for n, f in func:
        try:
            res.append((n, f()))
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


class PolicySummary(BaseModel):
    title: str = Field(
        ..., max_length=100, description="Title of the policy, brief, <=10 words"
    )

    key_takeaways: List[str] = Field(
        ..., max_items=4, description="Maximum 4 bullet points summarizing the policy"
    )

    pricing_and_market_access: List[str] = Field(
        ...,
        max_items=3,
        description=(
            "Maximum 3 bullet points addressing pricing and patient access impacts:\n"
            "- Potential effect on pricing of existing products and pipeline assets\n"
            "- Effect on patient access to medicines\n"
            "- Whether the policy acts as a cost-containment measure, accelerates access, or has negative implications"
        ),
    )

    pharma_pov_todos: List[str] = Field(
        ...,
        max_items=3,
        description=(
            "Maximum 3 concise bullet points suggesting potential actions for pharma companies and stakeholders:\n"
            "- Planning, implementation, and portfolio strategy adjustments\n"
            "- Mitigation or modeling strategies\n"
            "- Impact on launch sequence, commercialization, pricing, and access potential"
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

response_type_link_map = {
    (
        PolicyAnalysis.__name__,
        (
            "You are an expert policy analyst. Given the content of various policy documents, "
            "extract and summarize the key details into a structured format."
        ),
    ): ["phrma", "fda", "lexology", "goodwindlaw", "amcp"],
    (
        PolicySummary.__name__,
        """
You are tasked with analyzing a new healthcare or pharmaceutical policy. Provide the analysis in the following structured format:

1. **Title of the Policy:** Brief, not exceeding 10 words.
2. **Key Takeaways:** Maximum 4 bullet points summarizing the policy.
3. **Pricing and Market Access (P&MA) Impact:** Maximum 3 crisp bullet points addressing:
   * Potential effect on pricing of existing products and pipeline assets.
   * Effect on patient access to medicines.
   * Whether the policy acts as a cost-containment measure, accelerates access, or has negative implications.
4. **Point of View (PoV) on Pharma To-Dos:** Maximum 3 concise bullet points suggesting potential action items for pharma companies and stakeholders, including:
   * Planning, implementation, and portfolio strategy adjustments.
   * Mitigation or modeling strategies.
   * Impact on launch sequence, commercialization, pricing, and access potential.
Ensure the analysis is in English. If source content is in another language, translate it first before analysis.
Ensure all bullet points are crisp, actionable, and focused on strategic insights.

### Examples:
Council of the European Union and the European Parliament announced a provisional agreement on the landmark EU Pharma Package 
New regulatory data protection formula: from ‘8+2+1’ years to ‘8+1+1+1’ (+1 year for products demonstrating significant innovation)
New orphan drug exclusivity: 9 years (+2 for highly unmet medical needs)
Transferrable exclusivity vouchers for priority antibiotics (+1 year)
Extension of the Bolar exemption to marketing authorisation, health technology assessment, pricing and reimbursement, and tender submissions
Opportunity for regulatory sandboxes, to develop and test new and innovative therapies under the direct supervision of competent authorities
Shorter EMA approval timelines (from 210 to 180 days) 
New transparency obligations (drug supply and shortages, environmental impact, etc.)
Launch obligation: If a Member State requests the launch of a new medicine, the marketing authorisation holder (MAH) must comply within a year or lose market protection and face generic competition in that country
The political agreement is now subject to formal approval by the European Parliament and the Council 
P&MA impact 
Strikes a balance between promoting innovation and ensuring access to affordable medicines for patients across the EU
Shorter EMA approval timelines will likely accelerate patient access
A few of the provisions will likely erode competitiveness within the innovative sector and increase administrative burdens for innovator 
PoV on Pharma To-Dos
Assessment of how to integrate the new rules on regulatory exclusivities into their life cycle management (such as re-evaluating orphan pipeline), pricing/ market access and protection strategies 
Operationally equip themselves with a revised launch strategy (27-country preparedness model) 
Monitor generic participation in tenders even while under protection to anticipate the exact date of price erosion 
Conduct gap audits on CMC (Chemistry, Manufacturing, and Controls) data to ensure the environmental impact evidence is robust enough to pass an EMA audit 
 
Increased Cost-Effectiveness Threshold in the UK 
NICE’s cost-effectiveness range will increase from the current level of £20,000-30,000 to £25,000-35,000 per QALY, effective from April’2026 (doesn’t’ apply to Highly Specialised Technologies)
Clear process outlined for ongoing assessments: 
CE under current threshold >> proceed to recommendation  
Not CE under current threshold but likely under new threshold >> potentially pause until Apr’26  
Not likely CE under new threshold >> proceed as normal  
Previous negative recommendations can only be revisited with substantial new evidence as new threshold only won’t be sufficient  
New value set will be applied to the EQ-5D-5L health profile (with mapping to EQ-5D-3L) to convert patient-reported health states to numerical values to compare treatments on HRQoL and CE 
P&MA impact
Higher likelihood of NICE’s recommendations per year with the higher CE thresholds
While NICE's previous threshold and historically high VPAG rebate had kept UK drug prices relatively low however, higher CE threshold combined with the softening VPAG rebate and likely increased long-term NHS medicine costs might elevate UK’s role as list price anchor as part of International Reference Pricing baskets 
PoV on Pharma To-Dos
Manufacturers have the opportunity for re-evaluation of products with a negative recommendation, however, that entails substantial new evidence like RWE, long-term clinical data, or a new Patient Access Scheme (PAS) 
Re-evaluate UK's position in the global launch sequence as there will be a potential for higher list prices (or at least less aggressive discounts to hit the old £20k–£30k cap) 
Adopt the new EQ-5D-5L value set for all 2026+ submission 
 
Most Favored Nation (MFN) & The GENEROUS Model 
The GENEROUS Model (GENErating cost Reductions fOr U.S. Medicaid) is the primary vehicle for MFN implementation where manufacturers provide supplemental rebates to participating state Medicaid programs to match an international benchmark (second lowest GDP-adjusted net price among United Kingdom, France, Germany, Italy, Canada, Japan, Denmark, and Switzerland)
Applies to all single-source/innovator multiple-source drugs with Medicaid rebate agreement
Voluntary (5-year pilot, 2026–2030) for manufacturers with a Medicaid National Drug Rebate Agreement; manufacturers who participate get Uniform Coverage Criteria across all participating states
Supplemental rebates exclude Best Price/340B calculations 
P&MA impact
For new assets, the "launch early in the U.S., late in the EU" strategy is likely under pressure
Eliminates fragmented state Medicaid formulary battles 
PoV on Pharma To-Dos
Establish a Global Floor Price that accounts for the MFN multiplier 
Conduct NPV re-modeling for "Medicaid-heavy" assets using MFN-level net prices 
Prepare a TrumpRx / Cash-Pay Channel Strategy for portfolio products which should be diverted to the DTC channel to capture market share from PBM-excluded patients 
 
 
Germany's Medical Research Act 
Introduces optional confidential net reimbursement prices post-AMNOG (with 9% mandatory extra discount on the negotiated price + local R&D requirements: ≥5% trial patients in DEU or permanent research department in DEU)
Confidential pricing is elective (sunset 2028), public prices remain default/norm
Waives AMNOG "guardrails" for qualifying local R&D (reducing the rigidity of automatic price caps for minor/no added benefit)
Manufacturers only have 5 business days after the final GKV-SV price is set to opt for confidentiality 
P&MA impact
Reduces IRP leakage risk for opt-in products (breaks EU reference corridors for confidential deals) 
Parallel trade impact limited (most prices stay public; confidential rare due to 9% penalty) 
Forces deeper DEU discounts for confidentiality benefit 
PoV on Pharma To-Dos
Model confidential pricing NPV (9% discount vs IRP protection) 
Target ≥5% DE trial enrollment for guardrail waiver/free pricing 
Update EU price corridor models excluding confidential DE prices 

""",
    ): ["cms", "simon_kucher", "aifa"],
}


# ---- Load Text Files Safely ----
def load_policy_texts() -> List[dict[str, Part]]:
    parts = []
    texts = _scrape_all()
    for name, text in texts:
        try:
            if text:
                parts.append({name: Part.from_text(text=text)})
            else:
                st.warning(f"Text file for {name} is empty")
        except Exception as e:
            st.error(f"Failed to read {name}: {e}")
    return parts


# ---- Load or Call LLM ----
@st.cache_data(show_spinner=True)
def get_policy_analysis(parts: List[dict[str, Part]]):
    import json

    if not parts:
        raise ValueError("No policy content available to analyze.")
    res = []
    for (response_type, prompt), sources in response_type_link_map.items():
        valid_parts = [
            list(p.values())[0] for p in parts if any(s in p for s in sources)
        ]
        response_schema = (
            PolicyAnalysis
            if response_type == PolicyAnalysis.__name__
            else PolicySummary
        )
        path = f"policy_{response_type}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if existing_data:
                    return existing_data
        response = call_llm(
            prompt=prompt,
            contents=valid_parts,
            response_schema=list[response_schema],
        )
        rep = [response_schema.model_validate(i).model_dump() for i in response]
        for r in rep:
            for k, v in r.items():
                try:
                    val = v.strftime("%Y-%m-%d")
                    r[k] = val
                except:
                    continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=4)
        res.extend(rep)
    return res


st.set_page_config(page_title="Policy Analysis", layout="wide")

parts = load_policy_texts()
if not parts:
    st.error("No policy documents loaded. Please ensure scraping has run successfully.")
    st.stop()

try:
    pa_list = get_policy_analysis(parts)
except Exception as e:
    st.error(f"Failed to generate policy analysis: {e}")
    st.stop()
st.title("Policy Analysis", text_alignment="center")
for idx, item in enumerate(pa_list):

    if idx > 0:
        st.divider()

    # Branch based on model type
    try:
        item = PolicyAnalysis.model_validate(item)
    except pydantic.ValidationError:
        item = PolicySummary.model_validate(item)
    except Exception as e:
        st.error(f"Error validating item: {e}")
        continue
    if isinstance(item, PolicyAnalysis):

        with st.expander(item.policy_name, expanded=True):
            st.title(item.policy_name)
            with st.expander("View Sources"):
                for (response_type, prompt), name in response_type_link_map.items():
                    if response_type == PolicyAnalysis.__name__:
                        for n in name:
                            st.markdown(f"- {link_map[n]}")

            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Effective Date",
                    (
                        item.effective_date.strftime("%Y-%m-%d")
                        if item.effective_date
                        else "Not specified"
                    ),
                )
            with col2:
                st.metric(
                    "Proposal Date",
                    (
                        item.proposal_date.strftime("%Y-%m-%d")
                        if item.proposal_date
                        else "Not specified"
                    ),
                )

            st.header("Duration")
            st.write(item.duration or "Not specified")

            st.header("Policy Structure")
            for s in item.policy_structure:
                st.markdown(f"- {s}")

            st.header("Drug Eligibility Criteria")
            st.write(item.drug_eligibility_criteria)

            st.header("International Pricing Benchmark")
            st.write(item.international_pricing_benchmark)

            st.header("Benchmark Comparison")
            st.write(item.benchmark_comparison)

            st.header("Enforcement and Penalties")
            st.write(item.enforcement_and_penalties)

            col_left, col_right = st.columns(2)
            with col_left:
                st.header("What You Need to Know")
                for w in item.what_you_need_to_know:
                    st.markdown(f"- {w}")
            with col_right:
                st.header("Implications for Pharma Companies")
                for p in item.implications_for_pharma_companies:
                    st.markdown(f"- {p}")

    elif isinstance(item, PolicySummary):
        with st.expander(item.title, expanded=True):
            st.title(item.title)
            with st.expander("View Sources"):
                for (response_type, prompt), name in response_type_link_map.items():
                    if response_type == PolicySummary.__name__:
                        links = [link_map[n] for n in name]
                        s =[]
                        for l in links:
                            if isinstance(l, list):
                                s.extend(l)
                            else: s.append(l)
                        for link in s:
                            st.markdown(f"- {link}")
                            
            st.header("Key Takeaways")
            for k in item.key_takeaways:
                st.markdown(f"- {k}")

            st.header("Pricing & Market Access Impact")
            for p in item.pricing_and_market_access:
                st.markdown(f"- {p}")

            st.header("Pharma PoV / To-Dos")
            for t in item.pharma_pov_todos:
                st.markdown(f"- {t}")
