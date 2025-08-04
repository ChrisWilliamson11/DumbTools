from concurrent.futures import ThreadPoolExecutor
import json
import re
import requests
import os.path
import sys
import glob
from pathlib import Path

# Initialize variables


def downloadAsset(id):
    global current_file, num_to_download
    try:
        heads = {
            "authorization": "Bearer " + authToken,
            "content-type": "application/json;charset=UTF-8",
            "Accept": "application/json"
        }
        
        download_request_response = requests.post("https://quixel.com/v1/downloads", headers=heads, data=json.dumps({ "asset": id }))

        if (download_request_response.ok):
            print(f"  --> DOWNLOADING ITEM Item {id}")
        else:
            download_request_response = download_request_response.json()
            print(f"  --> ERROR: Unable to download {id} | [{download_request_response['code']}] {download_request_response['msg']}")
            return
        
        download_request_response = download_request_response.json()
        download_response = requests.get(f"http://downloadp.megascans.se/download/{download_request_response['id']}?url=https%3A%2F%2Fmegascans.se%2Fv1%2Fdownloads")

        if (not download_response.ok):
            download_response = download_response.json()
            print(f"  --> ERROR: Unable to download {id} | [{download_response['code']}] {download_response['msg']}")
            return

        filename = re.findall("filename=(.+)", download_response.headers['content-disposition'])[0]

        with open(filename, mode="wb") as file:
            file.write(download_response.content)

        print(f"  --> DOWNLOADED ITEM Item {id} | {filename} | {current_file} / {num_to_download}")
        current_file += 1

    except Exception as e:
        print(f"  --> ERROR: Download of {id} failed due to:", e)


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

current_file = 1
# 1. Set auth token, get cache, and init tracker variables
authToken = input("-> Auth Token >> ")

# Replace cache file reading with filesystem scanning
print("-> Scanning existing files...")
# First get all folder names once
folder_names = set()
for item in Path('.').rglob('*'):
    if item.is_dir():
        folder_names.add(item.name)

print("-> Get Acquired Items and filter existing...")
# Get acquired IDs once
acquired_ids = getAcquiredIds()
# Check each ID against folder names once
existing_assets = set(
    asset_id for asset_id in acquired_ids 
    if any(asset_id in folder_name for folder_name in folder_names)
)

# Filter the items
items = [x for x in acquired_ids if x not in existing_assets]

# 3. Get number to download
correct = False
num_to_download = len(items)
while not correct:
  num_to_download_input = input(f"-> How many of your {len(items)} assets do you want to download? (ALL to download everything) >> ")

  if num_to_download_input == "ALL":
    correct = True
  elif num_to_download_input.isnumeric():
    num_to_download_int = int(num_to_download_input)
    if num_to_download_int > 0 and num_to_download_int <= len(items):
      num_to_download = num_to_download_int
      correct = True
    else:
      print("-> ERROR: Input needs to be above 0 and below the total number of items you can download.")
  else:
    print("-> ERROR: Need to enter ALL or an integer.")


# 4. Get max number of workers and download items
# 3. Get number to download
correct = False
num_of_threads = 4
while not correct:
  num_of_threads_input = input(f"-> How many workers do you want? (ENTER to use 4) >> ")

  if num_of_threads_input == "":
    correct = True
  elif num_of_threads_input.isnumeric():
    num_of_threads_input_int = int(num_of_threads_input)
    if num_of_threads_input_int > 0:
      num_of_threads = num_of_threads_input_int
      correct = True
    else:
      print("-> ERROR: Input needs to be above 0 workers.")
  else:
    print("-> ERROR: Need to enter nothing or an integer.")

print(f"-> Downloading {num_to_download} assets...")

with ThreadPoolExecutor(max_workers=num_of_threads) as executor:
    executor.map(downloadAsset, items[0:num_to_download])

print(f"-> Downloaded {num_to_download} assets")

# 5. Done
print("-> DONE! Congrats on your new assets.")
print(f"--> There were {num_to_download - (current_file - 1)} errors.")






# eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImNocmlzLndpbGxpYW1zb24uaW5maW5pdHlAZ21haWwuY29tIiwic2NvcGUiOlsiZGVmYXVsdDp1c2VyIiwibWVnYXNjYW5zOnVzZXIiXSwic2NyZWVuTmFtZSI6ImNocmlzdyIsImxpbmtlZEVwaWNBY2NvdW50IjoiY2hyaXMud2lsbGlhbXNvbi5pbmZpbml0eUBnbWFpbC5jb20iLCJlcGljQWNjb3VudElkIjoiZjNmNmQ0MWJkOTk5NDIyYzhmYzdkNWQzNTcxYjdmMTMiLCJpc1VucmVhbEVVTEFBY2NlcHRlZCI6dHJ1ZSwiaXNFcGljQWNjb3VudCI6bnVsbCwicXVpeGVsQWNjb3VudElkIjoiMDQzNDQxNWEtYTAzZS00NmM5LTkxZjQtNDMzMmFkYWY1Y2EwIiwicmVhbG0iOiJtZWdhc2NhbnMiLCJldWxhc0FjY2VwdGVkIjpbInVlIiwibWhjIiwiZXBpY19jb250ZW50Il0sImlhdCI6MTcyOTIxNzY5MCwiZXhwIjoxNzI5MjQ2NDkwLCJpc3MiOiJxdWl4ZWwtc3NvLXByb2QiLCJqdGkiOiI1NWRjOGNhZi1mM2NkLTQ1YzctYWY0MC1jOWJkNDExNjM0NzcifQ.BgE66v70tKzwQWaD1s5Ct0rOhmb5-PuMV5zOKalQw2R3yIFdHJmIGb5wJAWULUXwSdsdH_aOMY9LrrMwns4RnTMCOdjSZJbHYF2xY9aZKPzO84vd0f-XP3HohojEonO3MKnPeEMstJj9V_4ugFLqw29yTwCU13VlXZQh76pr_f-LX83ev8D1um7YVso9RcICotC3hs4DA9fGNY-24pfobornWWd2JD3qdogENbZoo-n5jbgGbOJA92vYDzQRxhbgRDVJWJsKM0keKseC8mcRoTTUxOUx-CExcDpkvAUawuUxWciKoXQlqGFFGzYRd4QbTwsVpFKkLVOmUj9QixNHkA