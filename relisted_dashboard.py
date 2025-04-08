import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime, timedelta

# Zillow API headers
HEADERS = {
    "X-RapidAPI-Key": "c5b5ec9b92msh70992d8bd422aa4p1f0b09jsn69b538f7906c",
    "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
}

# Geocode address to get lat/lon (via Nominatim)
def geocode_address(address):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            return float(data["lat"]), float(data["lon"])
    except Exception:
        return None, None
    return None, None

# Get re-listed homes from Zillow
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
                lat, lon = geocode_address(address)
                link = f"https://www.zillow.com/homedetails/{zpid}_zpid/"
                all_relisted.append({
                    "Address": address,
                    "Price": price,
                    "Re-Listings (2yrs)": len(listings),
                    "Days on Zillow": days_on,
                    "Zillow Link": link,
                    "Latitude": lat,
                    "Longitude": lon
                })

    return all_relisted

# --- Streamlit App ---
st.set_page_config(page_title="Re-Listed Homes Finder", layout="wide")
st.title("🏡 Re-Listed Homes Finder")
st.write("Find properties listed multiple times on Zillow in the last 2 years.")

# Inputs
city = st.text_input("Enter City", "Los Angeles")
state = st.text_input("Enter State Abbreviation (e.g. CA)", "CA")
max_pages = st.slider("How many Zillow pages to search? (1 page ≈ 40 homes)", 1, 50, 5)

st.markdown("### Filters")
min_relistings = st.slider("Minimum Number of Re-Listings", 2, 5, 2)

# Format-friendly price inputs
min_price_str = st.text_input("Minimum Price ($)", "100,000")
max_price_str = st.text_input("Maximum Price ($)", "2,000,000")

try:
    min_price = int(min_price_str.replace(",", "").strip())
    max_price = int(max_price_str.replace(",", "").strip())
except ValueError:
    st.error("Please enter valid prices using numbers or commas (e.g., 150,000)")
    st.stop()

min_days_on_market = st.slider("Minimum Days on Market", 0, 365, 0)

# Search and results
if st.button("Search"):
    with st.spinner("Looking for re-listed homes..."):
        results = get_relisted_properties(
            city, state, max_pages,
            min_relistings, min_price, max_price, min_days_on_market
        )

        if results:
            df = pd.DataFrame(results)

            st.success(f"Found {len(df)} matching homes.")

            # Pagination
            page_size = 10
            total_pages = (len(df) + page_size - 1) // page_size
            page = st.number_input("Page", 1, total_pages, 1)
            start = (page - 1) * page_size
            end = start + page_size
            st.dataframe(df.iloc[start:end])

            # Download CSV
            csv = df.drop(columns=["Latitude", "Longitude"]).to_csv(index=False)
            st.download_button(
                label="📥 Download all results as CSV",
                data=csv,
                file_name=f"relisted_{city.lower()}_{state.lower()}.csv",
                mime="text/csv"
            )

            # Map View
            map_data = df.dropna(subset=["Latitude", "Longitude"])
            if not map_data.empty:
                st.markdown("### 🗺️ Map View")
                st.pydeck_chart(pdk.Deck(
                    initial_view_state=pdk.ViewState(
                        latitude=map_data["Latitude"].mean(),
                        longitude=map_data["Longitude"].mean(),
                        zoom=10,
                        pitch=0,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=map_data,
                            get_position="[Longitude, Latitude]",
                            get_radius=100,
                            get_fill_color=[200, 30, 0, 160],
                            pickable=True,
                        )
                    ],
                    tooltip={"text": "{Address}\n${Price}\nRe-Listings: {Re-Listings (2yrs)}"}
                ))
        else:
            st.warning("No re-listed homes found with those filters.")
