from concurrent.futures import ThreadPoolExecutor
import json
import re
import requests
import os.path
import sys
import glob
from pathlib import Path

# Initialize variables


def getAcquiredIds():
    heads = {
        "authorization": "Bearer " + authToken,
        "content-type": "application/json;charset=UTF-8",
        "Accept": "application/json"
    }

    response = requests.get("https://quixel.com/v1/assets/acquired", headers=heads)
    is_ok = response.ok
    response = response.json()
    
    if not is_ok:
        print(f"  --> ERROR: Error acquiring ids | [{response['statusCode']}] {response['message']}")
        sys.exit(0)

    return [x["assetID"] for x in response]

# Get auth token
authToken = input("-> Auth Token >> ")

# Get acquired IDs
print("-> Getting Acquired Items...")
acquired_ids = getAcquiredIds()
print(f"  --> Found {len(acquired_ids)} acquired assets")

# Write IDs to file
output_file = "megascans_asset_ids.txt"
with open(output_file, 'w') as f:
    for asset_id in acquired_ids:
        f.write(f"{asset_id}\n")

print(f"-> Successfully wrote {len(acquired_ids)} asset IDs to {output_file}")