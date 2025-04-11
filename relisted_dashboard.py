import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import time
from io import BytesIO

# Zillow API headers
HEADERS = {
    "X-RapidAPI-Key": "c5b5ec9b92msh70992d8bd422aa4p1f0b09jsn69b538f7906c",
    "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
}

def geocode_address(address):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json"}
        headers = {"User-Agent": "relisted-map-app"}
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            return float(data["lat"]), float(data["lon"])
    except Exception:
        pass
    return None, None

def process_property(home, two_years_ago, filters):
    zpid = home.get("zpid")
    if not zpid:
        return None

    try:
        detail_url = "https://zillow-com1.p.rapidapi.com/property"
        detail_query = {"zpid": str(zpid)}
        detail_response = requests.get(detail_url, headers=HEADERS, params=detail_query)
        if detail_response.status_code != 200:
            return None
        details = detail_response.json()

        price_history = details.get("priceHistory", [])
        facts = details.get("resoFacts", {})
        days_on = facts.get("daysOnZillow", 0)

        listings = [
            event for event in price_history
            if event.get("event") == "Listed for sale" and
               "date" in event and
               datetime.strptime(event["date"], "%Y-%m-%d") >= two_years_ago
        ]

        price = home.get("price") or 0
        if len(listings) >= filters["min_relistings"] and filters["min_price"] <= price <= filters["max_price"] and days_on >= filters["min_days_on_market"]:
            original_price = listings[-1].get("price") if listings else None
            price_diff = price - original_price if original_price else None
            percent_diff = ((price - original_price) / original_price * 100) if original_price and original_price != 0 else None

            address = home.get("address")
            lat, lon = geocode_address(address)
            time.sleep(1)

            return {
                "Address": address,
                "Price": f"${price:,.0f}",
                "Price Change ($)": f"${price_diff:,.0f}" if price_diff else "N/A",
                "Price Change (%)": f"{percent_diff:.1f}%" if percent_diff else "N/A",
                "Bedrooms": facts.get("bedrooms"),
                "Bathrooms": facts.get("bathrooms"),
                "Square Feet": facts.get("livingArea"),
                "Re-Listings (2yrs)": len(listings),
                "Days on Zillow": days_on,
                "Zillow URL": f"https://www.zillow.com/homedetails/{zpid}_zpid/",
                "Latitude": lat,
                "Longitude": lon
            }
    except:
        return None
    return None

def get_relisted_properties(location, page_limit, filters):
    all_props = []
    two_years_ago = datetime.now() - timedelta(days=730)

    for page in range(1, page_limit + 1):
        url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
        query = {
            "location": location,
            "status_type": "ForSale",
            "page": str(page)
        }
        response = requests.get(url, headers=HEADERS, params=query)
        if response.status_code != 200:
            continue
        data = response.json()
        props = data.get("props", [])

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(lambda home: process_property(home, two_years_ago, filters), props)
            all_props.extend([r for r in results if r])

    return all_props

# --- Streamlit UI ---
st.set_page_config(page_title="Re-Listed Homes Finder", layout="wide")
st.title("🏡 Re-Listed Homes Finder")
st.write("Find properties listed multiple times on Zillow in the last 2 years.")

zip_code = st.text_input("ZIP Code (optional)", "")
city = st.text_input("City", "Los Angeles") if not zip_code else ""
state = st.text_input("State Abbreviation (e.g. CA)", "CA") if not zip_code else ""
max_pages = st.slider("How many Zillow pages to search? (1 page ≈ 40 homes)", 1, 50, 5)

# Filters
st.markdown("### Filters")
min_relistings = st.slider("Minimum Number of Re-Listings", 1, 100, 2)
min_price_str = st.text_input("Minimum Price ($)", "100,000")
max_price_str = st.text_input("Maximum Price ($)", "2,000,000")

try:
    min_price = int(min_price_str.replace(",", "").strip())
    max_price = int(max_price_str.replace(",", "").strip())
except ValueError:
    st.error("Please enter valid prices using numbers or commas (e.g., 150,000)")
    st.stop()

min_days_on_market = st.slider("Minimum Days on Market", 0, 365, 0)

filters = {
    "min_relistings": min_relistings,
    "min_price": min_price,
    "max_price": max_price,
    "min_days_on_market": min_days_on_market
}

location = zip_code if zip_code else f"{city}, {state}"

if st.button("Search"):
    with st.spinner(f"Searching Zillow in {location}..."):
        results = get_relisted_properties(location, max_pages, filters)

        if results:
            df = pd.DataFrame(results)
            st.success(f"Found {len(df)} re-listed homes in {location}.")

            page_size = 10
            total_pages = (len(df) + page_size - 1) // page_size
            page = st.number_input("Page", 1, total_pages, 1)
            start = (page - 1) * page_size
            end = start + page_size

            st.markdown("### 📋 Results")
            for _, row in df.iloc[start:end].iterrows():
                st.markdown(f"""
**🏠 {row['Address']}**

💵 Price: {row['Price']}  
📉 Price Change: {row['Price Change ($)']} ({row['Price Change (%)']})  
🔁 Re-Listings: {row['Re-Listings (2yrs)']} | 🕒 Days on Zillow: {row['Days on Zillow']}  
🛏 {row['Bedrooms']} | 🛁 {row['Bathrooms']} | 📐 {row['Square Feet']} sqft  
🔗 [View on Zillow]({row['Zillow URL']})

---
""", unsafe_allow_html=True)

            # Excel download
            excel_df = df.drop(columns=["Latitude", "Longitude"])
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                excel_df.to_excel(writer, index=False, sheet_name="Re-Listed Homes")
                writer.close()
            st.download_button("📥 Download as Excel", data=output.getvalue(), file_name="relisted_properties.xlsx", mime="application/vnd.ms-excel")

            # Map
            map_data = df.dropna(subset=["Latitude", "Longitude"])
            if not map_data.empty:
                st.markdown("### 🗺️ Map View")
                avg_lat = map_data["Latitude"].mean()
                avg_lon = map_data["Longitude"].mean()
                zoom_level = 10
                lat_range = map_data["Latitude"].max() - map_data["Latitude"].min()
                lon_range = map_data["Longitude"].max() - map_data["Longitude"].min()
                if lat_range > 10 or lon_range > 10:
                    zoom_level = 4

                st.pydeck_chart(pdk.Deck(
                    initial_view_state=pdk.ViewState(
                        latitude=avg_lat,
                        longitude=avg_lon,
                        zoom=zoom_level,
                        pitch=0,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=map_data,
                            get_position="[Longitude, Latitude]",
                            get_radius=200,
                            get_fill_color=[0, 122, 255, 255],
                            pickable=True,
                        )
                    ],
                    tooltip={
                        "html": "<b>{Address}</b><br>"
                                "Price: {Price}<br>"
                                "Change: {Price Change ($)} ({Price Change (%)})<br>"
                                "🛏 {Bedrooms} | 🛁 {Bathrooms} | 📐 {Square Feet} sqft<br>"
                                "Re-Listings: {Re-Listings (2yrs)}"
                    }
                ))
        else:
            st.warning(f"No matching re-listed homes found in {location}.")
