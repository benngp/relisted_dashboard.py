 import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Your Zillow API headers
HEADERS = {
    "X-RapidAPI-Key": "c5b5ec9b92msh70992d8bd422aa4p1f0b09jsn69b538f7906c",
    "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
}

# Search Zillow API and return filtered results
def get_relisted_properties(city, state, page_limit, min_relistings, min_price, max_price, min_days_on_market):
    all_relisted = []
    two_years_ago = datetime.now() - timedelta(days=730)

    for page in range(1, page_limit + 1):
        url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
        query = {
            "location": f"{city}, {state}",
            "status_type": "ForSale",
            "page": str(page)
        }

        response = requests.get(url, headers=HEADERS, params=query)
        if response.status_code != 200:
            continue
        data = response.json()

        for home in data.get("props", []):
            zpid = home.get("zpid")
            if not zpid:
                continue

            # Lookup full property details
            detail_url = "https://zillow-com1.p.rapidapi.com/property"
            detail_query = {"zpid": str(zpid)}
            detail_response = requests.get(detail_url, headers=HEADERS, params=detail_query)
            if detail_response.status_code != 200:
                continue
            details = detail_response.json()

            price_history = details.get("priceHistory", [])
            days_on = details.get("resoFacts", {}).get("daysOnZillow", 0)

            listings = [
                event for event in price_history
                if event.get("event") == "Listed for sale" and
                   "date" in event and
                   datetime.strptime(event["date"], "%Y-%m-%d") >= two_years_ago
            ]

            price = home.get("price") or 0
            if len(listings) >= min_relistings and min_price <= price <= max_price and days_on >= min_days_on_market:
                address = home.get("address")
                link = f"https://www.zillow.com/homedetails/{zpid}_zpid/"
                all_relisted.append({
                    "Address": address,
                    "Price": price,
                    "Re-Listings (2yrs)": len(listings),
                    "Days on Zillow": days_on,
                    "Zillow Link": link
                })

    return all_relisted

# Streamlit UI
st.title("🏡 Re-Listed Homes Finder")
st.write("Find properties listed 2+ times on Zillow in the past 2 years.")

city = st.text_input("Enter City", "Los Angeles")
state = st.text_input("Enter State Abbreviation (e.g. CA)", "CA")
max_pages = st.slider("How many Zillow pages to search? (1 page ≈ 40 homes)", 1, 50, 5)

# Filter controls
st.markdown("### Filter Results")
min_relistings = st.slider("Minimum Number of Re-Listings", 2, 5, 2)
min_price = st.number_input("Minimum Price ($)", value=100000, step=50000)
max_price = st.number_input("Maximum Price ($)", value=2000000, step=50000)
min_days_on_market = st.slider("Minimum Days on Market", 0, 365, 0)

# Search button
if st.button("Search"):
    with st.spinner("Searching Zillow..."):
        results = get_relisted_properties(
            city, state, max_pages,
            min_relistings, min_price, max_price, min_days_on_market
        )

        if results:
            df = pd.DataFrame(results)

            # Pagination logic
            st.success(f"Found {len(df)} matching homes.")
            page_size = 10
            total_pages = (len(df) + page_size - 1) // page_size
            page = st.number_input("Results page", 1, total_pages, 1)
            start = (page - 1) * page_size
            end = start + page_size

            st.dataframe(df.iloc[start:end])

            # CSV download
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download all results as CSV",
                data=csv,
                file_name=f"relisted_{city.lower()}_{state.lower()}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No re-listed homes found that match your filters.")
