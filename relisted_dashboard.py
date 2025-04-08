import streamlit as st
import requests

# Your API headers
HEADERS = {
    "X-RapidAPI-Key": "c5b5ec9b92msh70992d8bd422aa4p1f0b09jsn69b538f7906c",
    "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
}

def get_relisted_properties(city, state, max_pages):
    all_relisted = []
    for page in range(1, max_pages + 1):
        url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
        query = {
            "location": f"{city}, {state}",
            "status_type": "ForSale",
            "page": str(page)
        }

        response = requests.get(url, headers=HEADERS, params=query)
        data = response.json()

        for home in data.get("props", []):
            history = home.get("priceHistory", [])
            if history and len(history) > 1:
                address = home.get("address")
                price = home.get("price")
                zpid = home.get("zpid")
                url = f"https://www.zillow.com/homedetails/{zpid}_zpid/"
                all_relisted.append({
                    "Address": address,
                    "Price": f"${price:,}",
                    "Zillow Link": url
                })

    return all_relisted

st.title("🏡 Re-Listed Homes Finder")
st.write("Find properties that have been re-listed on Zillow.")

city = st.text_input("Enter City", "Los Angeles")
state = st.text_input("Enter State Abbreviation (e.g. CA)", "CA")
max_pages = st.slider("Number of Result Pages to Search (1 page ≈ 40 listings)", 1, 5, 1)

if st.button("Search"):
    with st.spinner("Searching for re-listed homes..."):
        results = get_relisted_properties(city, state, max_pages)
        if results:
            st.success(f"Found {len(results)} re-listed homes in {city}, {state}.")
            st.dataframe(results)
        else:
            st.warning("No re-listed homes found.")
