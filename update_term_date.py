import sys
import requests
import urllib.parse
import os
import PyPDF2
import json
import datetime
import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk

CONSTANTS_FILE = 'constants.json'

# Open the file and read the contents
with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)

# save the api key
api_token = constants["apiToken"]
API_URL = constants["apiUrl"]


# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}" }

def main():
  course_id = 0
  offset = 0
  if len(sys.argv) > 1:
   course_id = sys.argv[1]
  else:
   course_id = tk.simpledialog.askinteger("What Course?", "Enter the course_id of the course (cut the number out of the url and paste here)")
  if len(sys.argv) > 2:
   offset = int(sys.argv[2])
  else:
   offset = tk.simpledialog.askinteger("How Many Days", "Enter the number of days to offset all assignment dates")

  assignments = get_paged_data(f"{API_URL}/courses/{course_id}/assignments?include=due_at")
  update_date_data = []
  for assignment in assignments:
    print(assignment["due_at"])
    due_at = datetime.datetime.fromisoformat(assignment["due_at"])
    due_at = due_at + datetime.timedelta(days=offset)
    response = requests.put(f"{API_URL}/courses/{course_id}/assignments/{assignment['id']}",
                            headers = headers,
                            json = {
          
          "assignment" : {
            "id" : assignment["id"],
            "due_at" : due_at.isoformat()
        }
      }
                            )
    if response.status_code == 200:
      print(f"Changed date of {assignment['name']} to {due_at}")
    else:
      print(f"Error changing date of {assignment['name']}")
      print(response.status_code)
      print(response.text)


def get_paged_data(url, headers=headers):
  response = requests.get(url, headers=headers)
  out = response.json()
  next_page_link = "!"
  while len(next_page_link) != 0:
      pagination_links = response.headers["Link"].split(",")
      for link in pagination_links:
        if 'next' in link:
          next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
          print(next_page_link)
          response = requests.get(next_page_link, headers=headers)
          out = out + response.json()
          break
        else:
          next_page_link = ""  
  print(len(out))

  return out

main()