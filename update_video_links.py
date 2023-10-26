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
from bs4 import BeautifulSoup

CONSTANTS_FILE = 'constants.json'

# Open the file and read the contents
with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)

# save the api key
api_token = constants["apiToken"]
api_url = constants["apiUrl"]


# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}" }

def main():
  course_id = 0

  if len(sys.argv) > 1:
   course_id = sys.argv[1]
  else:
   course_id = tk.simpledialog.askinteger("What Course?", "Enter the course_id of the old course (cut the number out of the url and paste here)")

  for i in range(1,9):
    old_url = f"{api_url}/courses/{course_id}/pages/week_{i}_learning_materials-2"
    new_url = f"{api_url}/courses/{course_id}/pages/week_{i}_learning_materials"
    old_page_response = requests.get(old_url, headers=headers)
    if old_page_response.status_code != 200:
      continue
    old_page = old_page_response.json()

    new_page_response = requests.get(new_url, headers=headers)
    new_page = new_page_response.json()

    old_soup = BeautifulSoup(old_page["body"], "html.parser")
    new_soup = BeautifulSoup (new_page["body"])
    old_iframe = old_soup.find("iframe")
    new_iframe = new_soup.find("iframe")
    youtube_iframe_source = old_iframe["src"]
    new_iframe["src"] = youtube_iframe_source
    print(youtube_iframe_source)
    print(new_iframe)

    response = requests.put(f'{api_url}/courses/{course_id}/pages/{new_page["page_id"]}', 
      headers = headers,
      data = {
        "wiki_page[body]" : new_soup.prettify()
      }
    )
    print(new_page["title"],response.status_code)


    


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