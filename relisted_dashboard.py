import streamlit as st
import requests
from datetime import datetime, timedelta

# Your Zillow API headers
HEADERS = {
    "X-RapidAPI-Key": "c5b5ec9b92msh70992d8bd422aa4p1f0b09jsn69b538f7906c",
    "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
}

def get_relisted_properties(city, state, max_pages):
    all_relisted = []
    two_years_ago = datetime.now() - timedelta(days=730)

    for page in range(1, max_pages + 1):
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

            # Lookup full property details using /property endpoint
            detail_url = "https://zillow-com1.p.rapidapi.com/property"
            detail_query = {"zpid": str(zpid)}
            detail_response = requests.get(detail_url, headers=HEADERS, params=detail_query)
            if detail_response.status_code != 200:
                continue
            details = detail_response.json()

            price_history = details.get("priceHistory", [])

            # Filter price history for "Listed for sale" events within 2 years
            recent_listings = [
                event for event in price_history
                if event.get("event") == "Listed for sale" and
                   "date" in event and
                   datetime.strptime(event["date"], "%Y-%m-%d") >= two_years_ago
            ]

            if len(recent_listings) >= 2:
                address = home.get("address")
                price = home.get("price")
                link = f"https://www.zillow.com/homedetails/{zpid}_zpid/"
                all_relisted.append({
                    "Address": address,
                    "Price": f"${price:,}" if price else "N/A",
                    "Zillow Link": link
                })

    return all_relisted

# Streamlit UI
st.title("🏡 Re-Listed Homes Finder")
st.write("Find properties that have been listed for sale 2+ times on Zillow in the past 2 years.")

city = st.text_input("Enter City", "Los Angeles")
state = st.text_input("Enter State Abbreviation (e.g. CA)", "CA")
max_pages = st.slider("How many Zillow pages to search? (1 page ≈ 40 homes)", 1, 5, 1)

if st.button("Search"):
    with st.spinner("Looking for re-listed homes..."):
        results = get_relisted_properties(city, state, max_pages)
        if results:
            st.success(f"Found {len(results)} re-listed homes in {city}, {state}.")
            st.dataframe(results)
        else:
            st.warning("No re-listed homes found in the last 2 years.")
