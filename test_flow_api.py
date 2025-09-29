"""
Test script for calling the BookFlow API endpoint.

This script demonstrates how to call the deployed BookFlow API with the correct
input structure matching the BookState model.
"""

import requests

# API configuration
# TODO: Replace with your actual deployment URL and bearer token
url = "https://write-a-book-with-flows-ad8a2655-fe9b-4553--28a0bd82.crewai.com"  # Replace with full URL from your interface
bearer_token = "b98081702280"  # Replace with your bearer token

headers = {
    "Authorization": f"Bearer {bearer_token}",
    "Content-Type": "application/json",
}

# Request body matching BookState structure
data = {
    "inputs": {
        # Optional: If you want to resume from a persisted state, include the id
        # "id": "1",
        # Optional: Override the default title
        "title": "Letters to My Daughter: A Father's Love in Verse",
        # Required: The topic for the book
        "topic": "A heartfelt collection of poems from fathers to their daughters, expressing unconditional love, pride, wisdom, and hopes for their daughters' futures",
        # Required: The goal describing what the book should accomplish
        "goal": """
            The goal of this poetry book is to capture the profound and tender love that fathers have for their daughters.
            Through carefully crafted verses, it will explore themes of unconditional love, protection, pride in watching
            daughters grow, life lessons fathers wish to impart, hopes and dreams for their daughters' futures, and the
            timeless bond between father and daughter. The book aims to provide fathers with words to express emotions
            that are sometimes hard to speak, and to give daughters a treasured keepsake that reminds them they are
            cherished, believed in, and forever loved. The poetry should be touching, sincere, and resonate with both
            fathers and daughters across all ages and stages of life. Create 2 chapters or less.
        """,
        # Optional: The following fields are typically populated during execution,
        # but can be provided if resuming a flow
        # "book": [],
        # "book_outline": [],
    }
}

# Make the request
try:
    print(f"Sending request to {url}/kickoff...")
    response = requests.post(f"{url}/kickoff", json=data, headers=headers)
    response.raise_for_status()

    result = response.json()
    kickoff_id = result.get("kickoff_id")

    print("\n✅ Success!")
    print(f"Kickoff ID: {kickoff_id}")
    print(f"\nYou can check the status at: {url}/status/{kickoff_id}")

except requests.exceptions.RequestException as e:
    print(f"\n❌ Error making request: {e}")
    if hasattr(e, "response") and e.response is not None:
        try:
            error_detail = e.response.json()
            print(f"Error details: {error_detail}")
        except:
            print(f"Response text: {e.response.text}")
except KeyError as e:
    print(f"\n❌ Expected key not found in response: {e}")
    print(f"Full response: {response.json()}")


# Example: Checking the status of a running flow
def check_status(kickoff_id: str):
    """Check the status of a running flow."""
    try:
        response = requests.get(f"{url}/status/{kickoff_id}", headers=headers)
        response.raise_for_status()

        status_result = response.json()
        print(f"\nStatus: {status_result.get('status')}")

        if status_result.get("status") == "completed":
            print("\n📚 Generated Book:")
            print(status_result.get("output", "No output available"))

        return status_result

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error checking status: {e}")
        return None


# Uncomment to check status after kickoff
# if 'kickoff_id' in locals():
#     import time
#     time.sleep(5)  # Wait a bit before checking
#     check_status(kickoff_id)
