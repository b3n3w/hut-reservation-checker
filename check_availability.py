import os
import json
import requests
from time import sleep

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HUTS = os.environ.get("HUTS", "")  # e.g. "150,603"
DATES_JSON = os.environ.get("DATES", "[]")  # e.g. '[{"arrivalDate":"11.07.2025","departureDate":"12.07.2025"}]'
FREE_BEDS = os.environ.get("FREE_BEDS", "3")

BASE_URL = "https://www.hut-reservation.org/api/v1"

# Parse input
selected_hut_ids = [int(h.strip()) for h in HUTS.split(",") if h.strip().isdigit()]
dates = json.loads(DATES_JSON)

def get_hut_info(hut_id):
    url = f"{BASE_URL}/reservation/hutInfo/{hut_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Failed to fetch hut info for {hut_id}: {e}")
        return None

def check_availability(hut_id, hut_name, categories, arrival, departure):

    url = f"{BASE_URL}/reservation/checkAvailability/{hut_id}"

    category_ids = [c["categoryID"] for c in categories]
    peoplePerCategory = [{"categoryId": id, "people": 0} for id in category_ids]

    payload = {
        "arrivalDate": arrival,
        "departureDate": departure,
        "numberOfPeople": 0,
        "nextPossibleReservations": False,
        "peoplePerCategory": peoplePerCategory,
        "isWaitingListAccepted": False,
        "reservationPublicId": ""
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.hut-reservation.org",
        "Referer": "https://www.hut-reservation.org/reservation"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        availabilityPerDayDTOs = data.get("availabilityPerDayDTOs", [{}])
        categories = availabilityPerDayDTOs[0].get("bedCategoriesData", [])

        for category in categories:
            label_data = category.get("hutBedCategoryLanguagesData", [])
            category_label = next((l["label"] for l in label_data if l["language"] == "EN"), "Unknown Category")
          
            total_beds = category.get("totalPlaces", 0)
            free_beds = category.get("totalFreePlaces", 0)

            if free_beds > int(FREE_BEDS):
                print(category)
                send_discord_notification(hut_name, arrival, departure, category_label , free_beds)
            elif free_beds == 0:
                print(f"{arrival}–{departure} | {hut_name} ({category_label}): No beds availble — no notification.")
            else:
                print(f"{arrival}–{departure} | {hut_name} ({category_label}): Only {free_beds} beds availble — no notification.")

    except requests.RequestException as e:
        print(f"Error checking availability for {hut_name} ({category_label}) {arrival}–{departure}: {e}")

def send_discord_notification(hut_name, arrival, departure, category_label, free_places):
    message = {
        "content": f"🛌 **{free_places} beds** available in **{category_label}** at **{hut_name}** from {arrival} to {departure}!\n👉 https://www.hut-reservation.org"
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        response.raise_for_status()
        print(f"✅ Notification sent for {hut_name} ({category_label}) from {arrival} to {departure}.")
    except requests.RequestException as e:
        print(f"❌ Failed to send Discord message: {e}")

if __name__ == "__main__":

    if not selected_hut_ids:
        print("No valid hut IDs provided.")

    if not dates:
        print("No valid date ranges provided.")


    for hut_id in selected_hut_ids:
        hut_info = get_hut_info(hut_id)

        if not hut_info:
            continue

        hut_name = hut_info.get("hutName", f"Hut {hut_id}")

        categories = [
            c for c in hut_info.get("hutBedCategories", [])
            if c.get("isVisible", False)
        ]

        if not categories:
            print(f"No visible categories found for {hut_name}")
            continue

        for date in dates:
            check_availability(
                hut_id=hut_id,
                hut_name=hut_name,
                categories=categories,
                arrival=date["arrivalDate"],
                departure=date["departureDate"]
            )
