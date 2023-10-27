import sys
import re
import requests
from  urllib.parse import urlparse, urlunparse
import os
import PyPDF2
import json
import datetime
import copy
import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk
from bs4 import BeautifulSoup

CONSTANTS_FILE = 'constants.json'
ADD_LEARNING_MATERIALS = False
UPDATE_SYLLABUS = True

# Open the file and read the contents
try:
  with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)
except:
  tk.messagebox.showerror(message="Problem loading constants.json. Ask hallie for a copy of constants.json and put it in this folder.")
# save the api key
api_token = constants["apiToken"]
api_url = constants["apiUrl"]
account_id = 169877

# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}" }

def main():
  course_id = 0
  old_course_id = 0


  #course = response.json()

  if len(sys.argv) > 1:
   course_id = sys.argv[1]
  else:
   course_id = tk.simpledialog.askinteger("What Course?", "Enter the course_id of the new ourse (cut the number out of the url and paste here)")


  url = f"{api_url}/courses/{course_id}"
  print(url)
  response = requests.get(url, headers=headers)
  if response.status_code != 200:
    tk.messagebox.showinfo("report", f"Course not found.\n{response.text}")
    exit()
  course = response.json()

  if len(sys.argv) > 2:
   old_course_id = sys.argv[2]
  #else:
  # old_course_id = tk.simpledialog.askinteger("Old Version of Course?", "Enter the course_id of the old course (cut the number out of the url and paste here)")

  if not old_course_id or old_course_id == 0:
    code = course["course_code"].split("_")[1]
    print(code)
    response = requests.get(f"{api_url}/accounts/{account_id}/courses", headers=headers, params = {"search_term" : f"DEV_{code}"} )
    courses = response.json()

    for course in courses:
      print(course["course_code"])
    if len(courses) > 0:
      old_course_id = courses[0]["id"]

  print("Found old course ", old_course_id, courses[0]["name"])



  if ADD_LEARNING_MATERIALS:
    update_learning_materials(course_id)

  if UPDATE_SYLLABUS:
    update_syllabus_and_overview(course_id, old_course_id)

def update_syllabus_and_overview(course_id, old_course_id):
  old_page = get_syllabus(old_course_id)
  title = find_syllabus_title(old_page)
  description_paras = get_section(old_page, "Course Description:")
  learning_objectives_paras = get_section(old_page, "Course Outcomes:")
  textbook_paras = get_section(old_page, "Textbook:")

  #update the new syllabus
  #new_page = get_syllabus(course_id)
  #set_week_1_preview(new_page, get_week_1_preview(course_id))
  #set_syllabus_description(new_page, description)
  #set_syllabus_learning_objectives(new_page, learning_objectives)
  #set_syllabus_dates(new_page, start_date, end_date, term_code)
  #update_grading(new_page, is_course_grad)


  #update the new overview


def get_syllabus(course_id):
  url = f"{api_url}/courses/{course_id}?include[]=syllabus_body"
  response = requests.get(url, headers=headers)
  content = response.json()
  return BeautifulSoup(content["syllabus_body"])

def find_syllabus_title(soup):
  header = soup.find("strong", string=re.compile("course number and title", re.IGNORECASE))
  title_p = header.find_parent("p")
  header.decompose()
  return title_p.text

def get_section(soup, header_string):
  header = soup.find("h4", string=header_string)
  paragraphs = []
  el =  header.find_next_sibling()
  print(el.name)
  while el and el.name != "h4":
    paragraphs.append(el)
    el = el.find_next_sibling()
  return paragraphs


#https://codereview.stackexchange.com/questions/272811/converting-a-youtube-embed-link-to-a-regular-link-in-python
def convert_to_watch_url(embed_url: str) -> str:
    """Convert a YouTube embed URL into a watch URL."""

    scheme, netloc, path, params, query, fragment = urlparse(embed_url)
    video_id, path = Path(path).stem, '/watch'
    return urlunparse((scheme, netloc, path, params, f'v={video_id}', fragment))


def get_week_1_preview(course_id):

    old_lm_url = f"{api_url}/courses/{course_id}/pages/week_1_learning_materials-2"
        #handle transcripts
    h4 = old_soup.find("h4")
    learning_materials = list(h4.next_siblings)
    lm_response = requests.get(old_lm_url, headers=headers)
    lm_page = lm_response.json()
    lm_soup = BeautifulSoup(lm_page["body"])

    iframe = lm_soup.find("iframe")
    youtube_iframe_source = iframe["src"]
    transcripts = lm_soup.find_all("div", {'class':"column"})[1].find_all("a", re.compile("Transcript", re.IGNORECASE))
    slides = lm_soup.find_all("div", {'class':"column"})[1].find_all("a", re.compile("Slides", re.IGNORECASE))

    temp_soup = BeautifulSoup(f"<li><a href={convert_to_watch_url(youtube_iframe_source)}>Week 1 Lecture</a><ul></ul></li>")
    list_ = temp_soup.find("ul")
    for transcript in transcripts:
      li = temp_soup.new_tag("li")
      a = temp_soup.new_tag("a")
      a["body"] = "transcript"
      a["href"] = transcript["href"]
      li.appended(li)
      list_.append(li)
    for slide in slides:
      li = temp_soup.new_tag("li")
      a = temp_soup.new_tag("a")
      a["body"] = "slides"
      a["href"] = slide["href"]
      li.appended(li)
      list_.append(li)

    learning_materials[0].insert( 0, temp_soup.html.body.li )


def update_learning_materials(course_id):
  for i in range(1,9):
    old_url = f"{api_url}/courses/{course_id}/pages/week_{i}_learning_materials-2"
    new_url = f"{api_url}/courses/{course_id}/pages/week_{i}_learning_materials"

    old_page_response = requests.get(old_url, headers=headers)
    if old_page_response.status_code != 200:
      continue
    old_page = old_page_response.json()

    new_page_response = requests.get(new_url, headers=headers)
    new_page = new_page_response.json()

    old_soup = BeautifulSoup(old_page["body"])
    new_soup = BeautifulSoup (new_page["body"])
    
    #handle youtube links
    old_iframe = old_soup.find("iframe")
    new_iframe = new_soup.find("iframe")
    youtube_iframe_source = old_iframe["src"]
    new_iframe["src"] = youtube_iframe_source


    old_header = old_soup.find("h4")
    learning_materials = list(old_header.next_siblings)
    
    #handle transcripts
    transcripts_and_slides = old_soup.find_all("div", {'class':"column"})[1].find_all("a")

    buttons = new_soup.find_all("p", { "class" : "cbt-button"})
    slides_button = None
    transcript_button = None

    for button in buttons:
      if button.find("a", string=re.compile("Slides",re.IGNORECASE)):
        slides_button = button.find("a", string=re.compile("Slides",re.IGNORECASE))
      if button.find("a", text=re.compile("Transcript", re.IGNORECASE)):
        transcript_button = button.find("a", string=re.compile("Transcript", re.IGNORECASE))


    slides_count = 0
    transcripts_count = 0
    old_transcript_button = None
    for element in transcripts_and_slides:

      if element.find(string=re.compile("Transcript", re.IGNORECASE)):
        if (transcripts_count > 0):
          old_button = transcript_button
          old_button["body"] = f"Transcript {transcripts_count}"
          button_container = copy.copy(old_button.parent)
          old_button.parent.parent.append(button_container)
          transcript_button = button_container.find('a')
          transcript_button["body"] = f"Transcript {transcripts_count + 1}"

        #replace link
        transcript_button["href"] = element["href"]
        transcripts_count = transcripts_count + 1

      if element.find(string=re.compile("Slides", re.IGNORECASE)):
        if (slides_count > 0):
          old_button = slides_button
          old_button["body"] = f"Slides {slides_count}"
          button_container = copy.copy(old_button.parent)
          old_button.parent.parent.append(button_container)
          slides_button = button_container.find('a')
          slides_button["body"] = f"Slides {slides_count + 1}"

        #replace link
        slides_button["href"] = element["href"]
        slides_count = slides_count + 1



      print("adding Learning Materials")
      #handle learning materials
      accordion = new_soup.find("div", class_="cbt-accordion-container")

      #make a new accordion and just all the learning materials into it
      new_content = copy.copy(accordion)
      accordion.parent.append(new_content)
      content = new_content.find("div", class_="cbt-answer")
      for el in learning_materials:
        content.append(el)
        print(content)
        print(el)



    #save changes
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