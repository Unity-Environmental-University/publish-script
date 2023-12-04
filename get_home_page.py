import re
from bs4 import BeautifulSoup
import docx
import sys
import requests
import urllib.parse
import zipfile
import os
import PyPDF2
import json
import webbrowser

import win32com.client as win32   

import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk

from PIL import Image

def log(output):
  print(output)


CONSTANTS_FILE = 'constants_test.json'

max_profile_image_size = 400
# Open the file and read the contents
with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)

log_filename = "log.txt"

# save the api key
api_token = constants["apiToken"]
api_url = constants["apiUrl"]
html_url = re.sub('\/api\/v1', '', constants["apiUrl"])
log(html_url)

instructor_course_id = constants["instructorCourseId"]
profile_assignment_id = constants["profileAssignmentId"] 
profile_pages_course_id = constants["profilePagesCourseId"]

default_profile_url = "https://unity.instructure.com/users/9230846/files/156109264/preview"
live_url = constants["liveUrl"]

# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}" }
live_headers = {"Authorization": f'Bearer {constants["liveApiToken"]}' }

log_string = ""

def main():




  number = 0
  if len(sys.argv) > 1:
    number = sys.argv[1]
  else:
    number = tk.simpledialog.askinteger("What Course?", "Enter the course_id of the blueprint (cut the number out of the url and paste here)")


  bp_id = number

  root = tk.Tk()
  message_label = tk.Label(root, text="Processing...")
  message_label.pack()

  # Create a progress bar
  progress_bar = ttk.Progressbar(root, orient="horizontal", length=200, mode="determinate")
  progress_bar.pack()

  bp_course = get_course(bp_id)
  courses = get_blueprint_courses(bp_id)
  log(courses)

  if tk.messagebox.askyesno(message=f"Do you want to remove lm annotations from {bp_course['name']}?"):
    remove_lm_annotations_from_course(bp_course["id"])

  if tk.messagebox.askyesno(message="Do you want to lock module items?"):
    lock_module_items(bp_id)

  #if the course has no associations, JUST queue up to update the input course
  if not courses:
    if tk.messagebox.askyesno(message=f"Course {bp_course['name']} does not have associated courses. Do you want to just get the bio for this course?"):
      courses = [bp_course]
    else:
      exit()

  force = True if "force_import" in sys.argv else False if "bypass_import" in sys.argv else tk.messagebox.askyesno(message="Do you want to import current profile data?")


  pages = get_faculty_pages(force=force)

  profiles = replace_faculty_profiles(courses, pages, root, progress_bar)

  bio_count = 0
  error_text = ""
  emails = []
  for profile in profiles:
    if not profile:
      error_text = error_text + "A course does not have a user associated"
      continue
    if len(profile["bio"]) < 5:
      error_text = error_text + f'{profile["user"]["name"]} does NOT have a bio we can find\n'
    else:
      bio_count = bio_count + 1
      if "email" in profile["user"]:
        emails.append(profile["user"]["email"])
      else:
        error_text = error_text + ("\nNo Email Found for " + profile["user"]["name"])
  dialog_text = f"Finished, {bio_count} records updated successfully\n{error_text}"

  with open("email_template.html", 'r') as f:
    template = f.read()


  base_course = courses[0]
  code = bp_course["course_code"][3:]

  tk.messagebox.showinfo("report", dialog_text)


 
  if tk.messagebox.askyesno(message="Do you want to try to generate an email?"):
    email_subject = f'{bp_course["course_code"][3:]} Section(s) Ready Notification'
    email_body = template.format(
      term = constants["term"],
      creator = constants["creator"],
      code = code,
      course = base_course,
    )  
    text = f'''
    
    {','.join(emails)}

    {email_subject}

    {email_body}
    '''

    text = re.sub('<\/?\w+>', '', text)
    log(text)


    try:
      outlook = win32.Dispatch('outlook.application')
      mail = outlook.CreateItem(0)
      for recipient in emails:
         mail.Recipients.Add(recipient).Type = 3  
      #Email.Bcc = ",".join(emails)
      mail.Subject = email_subject
      mail.HtmlBody = email_body
      mail.Display()
    except Exception as e:
      #webbrowser.open(f'mailto:hallie@gmail.org?bcc={",".join(emails)}&subject={email_subject}&body={email_body}', new=1)
      with open("email.txt","w") as file:
        file.write(text)
      tk.messagebox.showerror(message="Error Generating Email. Text was written to 'email.txt' ")





def lock_module_items(course_id):
  modules = get_modules(course_id)
  for module in modules:
    for item in module['items']:
      url= f"{api_url}/courses/{course_id}/blueprint_templates/default/restrict_item"
      log(url)
      id_ = ""
      print
      type_ = item["type"]
      if type_ == "Assignment":
        type_ = "assignment"
        id_ = item["content_id"]
      elif type_ == "Discussion":
        type_ = "discussion_topic"
        id_ = item["content_id"]
      elif type_ == "Quiz":
        type_ = "quiz"
        id_ = item["content_id"]
      elif type_ == "Attachment":
        type_ = "attachment"
        id_ = item["content_id"]
      elif type_ == "External Tool":
        type_ = "external_tool"
        id_ = item["content_id"]
      elif type_ == "Page":
        type_ = "wiki_page"
        page_url = item["url"]
        response = requests.get(page_url, headers=headers)
        log(response)
        if response.ok and response.status_code == 200:
          log(response.json())
          id_ = response.json()["page_id"]
      elif type_ == "File":
        type_ = "file"
        id_ = item["content_id"]
      else:
        continue


      response = requests.put(url, headers=headers, data={
        "content_type" : type_,
        "content_id" : id_,
        "restricted" : True,
        })
      if response.ok:
        log(response.json())
      else:
        log(response)
        log(response.text)
        log(json.dumps(item, indent=2))


def remove_lm_annotations_from_course(course_id):
  modules = get_modules(course_id)
  for module in modules:
    #find an item in the module called "Week ? Learning Materials"
    lm_page = next( (filter(lambda item: item['type'] == 'Page' and re.search(r'Week \d+ Learning Materials', item['title']), module['items'] )), None)
    if lm_page:
      full_page = requests.get(lm_page['url'], headers=headers).json()

      body = remove_lm_annnotations(full_page['body'])
      #print(json.dumps(full_page, indent=2))
      print(lm_page['url'])
      data = {
        'wiki_page[body]' : body
       }
      print(data)
      response = requests.put(lm_page['url'], headers=headers, 
      data=data)

      print(response.text)

def remove_lm_annnotations(text):

  #one liners to replace
  replacements = [
    {
      'find' : r'<p>\[Text for optional primary media element to be written by SME\]</p>',
      'replace' : '',
    },

    {
      'find' : r'\[[iI]nsert annotation for media\]',
      'replace' : '',
    },
  ]
  
  for replace in replacements:
    find = re.compile(replace['find'], flags=re.MULTILINE)
    print(replace['find'])
    text=re.sub('\\n', '\n', text)
    text = re.sub(r'(\s)\s+', '\1', text)
    match = re.findall(find, text.format())
    if match:
      print("FOUND", match)
      text = re.sub(find, replace['replace'], text)

  #remove these sections
  soup = BeautifulSoup(text, 'lxml')
  bq = soup.find('blockquote')
  if bq and "SME" in bq.text:
    parent = single_filter(lambda item: item.has_attr('class') and 'cbt-content' in item['class'], bq.parents)
    print(parent)
    parent.decompose()

  divs = soup.find_all('div')
  div = single_filter(lambda item: item.has_attr('class') and 'cbt-content' in item['class'] and '[LM Narrative' in item.text, divs)
  if div:
    div.decompose()

  out = str(soup.find('body') )
  out = re.sub(r'</?body>', '', out)
  return out


def single_filter(func, set, default = None):
  return next(filter( func, set), None)

def get_modules(course_id):
  url = f"{api_url}/courses/{course_id}/modules?include[]=items&include[]=content_details"
  log(url)
  return get_paged_data(url)

def replace_faculty_profiles(courses, pages, ui_root, progress_bar):
  profiles = []
  i = 1
  for course in courses:

    profile = get_course_profile(course, pages)
    profiles.append(profile)

    overwrite_home_page(profile, course)
  
    #update loading UI value after processing
    ui_root.update_idletasks()     
    ui_root.update()
    progress_bar["value"] = (i / len(courses)) * 100
    i = i + 1

  return profiles

def save_bios(bios, path="bios.json"):
  with open(path, 'w') as f:
    json.dump(bios, f, indent=2)

def get_faculty_pages(force=False):
  log(force)
  if os.path.isfile("bios.json") and not force:
    with open("bios.json", 'r') as f:
      pages = json.load(f)
      log(len(pages))
  else:
    pages = get_paged_data(f"{live_url}/courses/{profile_pages_course_id}/pages?per_page=50&include=body", live_headers)
    save_bios(pages)    
  return pages

def get_course(course_id):
  url = f'{api_url}/courses/{course_id}'
  response = requests.get(url, headers=headers)
  log(response)
  return response.json()


def format_profile_page(profile, course, homepage):
  text = ""
  #if it's cbt theme, run the new formatter
  if "cbt-banner-header" in homepage['body']:
    text = format_profile_page_newdev(profile, course, homepage)
  else:
    with open("template.html", 'r') as f:
      template = f.read()
    text = template.format(
      course_title = homepage["title"] if "title" in homepage else f' Welcome to {course["name"]}',
      instructor_name = profile["display_name"] if "display_name" in profile else profile["user"]["name"],
      img_src = profile["img_src"],
      bio=profile["bio"])

  text = clean_up_bio(text)
  with open(f'profiles/{profile["user"]["id"]}_{course["id"]}.htm', 'wb') as f:
    f.write(text.encode("utf-8", "replace"))

  return text

def clean_up_bio(html):
  html = re.sub(r'<p>\w*(&nbsp;)?\w*</p>','', html)
  return html

def format_profile_page_newdev(profile, course, homepage):
  body = homepage['body']
  instructor_name = profile["display_name"] if "display_name" in profile else profile["user"]["name"]
  bio_body = profile["bio"]
  data_url = re.sub('.com/', '.com/ap1/v1/', profile['img_src']) #change to api instead of site url
  body = re.sub(r'<p>\w*<span>\w*Instructor bio coming soon!\w*</span>\w*</p>', bio_body, body)
  #replace image
  find_profile_image = re.compile(r'src="[^"]*"([^>]*)alt="male-profile-image-placeholder.png" data-api-endpoint="[^"]*"')
  homepage = re.sub(find_profile_image, f'src="{profile["img_src"]}"\1data-api-endpoint="{data_url}"', body)

  return homepage

def get_course_profile(course, pages):
  return get_course_profile_from_pages(course, pages)

def get_course_profile_from_pages(course, pages):
  instructor = get_canvas_instructor(course["id"])


  prompt = f'No instructor found for {course["name"]} do you want to to search for an instructor by name?'
  if not instructor:
    while tk.messagebox.askyesno(message=prompt):
      name = tk.simpledialog.askstring(title="Name", prompt="Please enter the full user name of the person you would like to find")
      users = []
      result = requests.get(f"{api_url}/accounts/self/users?search_term={name}", headers=headers)
      if result.ok and len(result.json()) > 0:
        for user in result.json():
          if tk.messagebox.askyesno(message=f"Do you want to use {user['name']}?"):
            instructor = user
            break
        if instructor:
          break
      else:
        log(result)
        log(result.json())
        prompt = f"No results found for {name}. Do you want to search for another instructor?"
    if not instructor:    
      return None
  course_id = course["id"]
  profile = get_instructor_profile_from_pages(instructor, pages)

  if not profile or len(profile["bio"]) == 0:
    profile = get_instructor_profile_submission(instructor)
  return profile



def get_course_profile_from_assignment(course):
  instructor = get_canvas_instructor(course["id"])
  course_id = course["id"]
  if instructor is not None:
    log("The instructor of the course {} is {}".format(course_id, instructor))
  else:
    log("The instructor of the course {} cannot be found.".format(course_id))
  return get_instructor_profile_submission(instructor)


def get_blueprint_courses(bp_id):
  url = f"{api_url}/courses/{bp_id}/blueprint_templates/default/associated_courses?per_page=50"
  response = requests.get(url, headers=headers)
  courses = response.json()

  if "errors" in courses:
    log(courses["errors"])
    return False

  next_page_link  = "!"
  while len(next_page_link) != 0 and "link" in response.headers:
    pagination_links = response.headers["Link"].split(",")
    for link in pagination_links:
      if 'next' in link:
        next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
        response = requests.get(next_page_link, headers=headers)
        courses = courses + response.json()
        log("added courses at", next_page_link )
        break
      else:
        next_page_link = ""
      log(link)


  return courses

def overwrite_home_page(profile, course):
  # Make a GET request to the Canvas LMS API to get the homepage of the course.
  url = f'{api_url}/courses/{course["id"]}/front_page'
  page_url = f'{html_url}/courses/{course["id"]}/'
  log(page_url)
  response = requests.get(url, headers=headers)

  # Check the response status code.
  if response.status_code != 200:
    raise ValueError('Failed to get homepage of course: {}'.format(response.status_code))

  webbrowser.open(page_url, new=1)


  # Parse the homepage HTML content.
  
  homepage_html = response.json()['body']
  homepage = { "course_title" : None, "body" : homepage_html }
  soup = BeautifulSoup(homepage_html, 'html.parser')
  h2Tags = soup.find_all('h2')
  if len(h2Tags) > 0:
    homepage["title"] = h2Tags[0].text

  if profile:
    data = {'wiki_page[body]': format_profile_page(profile, course, homepage)}

    response = requests.put(url, headers=headers, data=data)
    log(response)
  else:
    log("instructor not found for this course; skipping")



def get_instructor_profile_from_pages(user, pages):
  first_name = user["name"].split(" ")[0]
  last_name = user["name"].split(" ")[-1]

  def restrictive_filter_func(entry):
    return user["name"].lower() in entry["title"].lower()
  def premissive_filter_func(entry):
    return last_name.lower() in entry["title"].lower() and first_name.lower() in entry["title"].lower()
  def extremely_permissive_filter_func(entry):
    return last_name.lower() in entry["title"].lower() or first_name.lower() in entry["title"].lower()

  prompt_user = False
  potentials = list(filter(restrictive_filter_func, pages))
  if len(potentials) == 0:
    potentials = list(filter(premissive_filter_func, pages))

  if len(potentials) == 0:
    prompt_user = True #Prompt the user to check this/these names because we've used the extremely permissive function
    potentials = list(filter(extremely_permissive_filter_func, pages))


  out = dict( user=user, bio = "", img = "", img_src = "")
  page = None

  if len(potentials) > 1 or prompt_user:
    log(json.dumps(user, indent=2))
    log("_________________POTENTIALS______________________")
    log(json.dumps(potentials, indent=2))
    log("----------------------------------------------------")

    for potential in potentials:
      if not "body" in potential:
        continue
      if tk.messagebox.askyesno(message=f"No direct match found for {user['name']}. Do you want to use { potential['title'] }?"):
        page = potential
  else:
    page = potentials[0]


  if not page:
    tk.messagebox.showinfo(message=f"No profile found matching {user['name']}")
    return False

  html = page["body"]
  soup = BeautifulSoup(html, 'html.parser')

  h4_tags = soup.find_all('h4')

  # Iterate over the h4 tags and find the next sibling paragraph tag
  paragraphs = []
  bio = ""
  for h4_tag in h4_tags:
      if "instructor" in h4_tag.text.lower():
        next_sibling = h4_tag.find_next_sibling('p')
        while next_sibling is not None:
          paragraphs.append(next_sibling.text)
          next_sibling = next_sibling.find_next_sibling('p')

  # Create the bio output
  for paragraph in paragraphs:
      bio = f"{bio}\n<p>{paragraph}</p>"
  out["bio"] = bio

  #get display name just in case
  out["display_name"] = False
  for p in soup.find_all('p'):
    previous_p = p.find_previous_sibling('p')
    if "instructor" in p.text.lower() and previous_p is not None:
      print (previous_p.text)
      out["display_name"] = previous_p.text

  #get image output
  imgs = soup.find_all("img")
  for img in imgs:
    out["img_src"] = img["src"]

  return out


def get_instructor_profile_submission(user):
  url = f"{api_url}/courses/{instructor_course_id}/assignments/{profile_assignment_id}/submissions/{user['id']}"
  response = requests.get(url, headers=headers)
  submission = response.json()
  log(submission)
  bio = submission["body"] if ("body" in submission and submission["body"] is not None) else ""
  pic_path = ""
  if "attachments" in submission:
    for attachment in submission["attachments"]:
      url = attachment["url"]
      attachmentData = requests.get(url, headers=headers)

      filename = attachment["filename"]
      with open (filename, 'wb') as f:
        f.write(attachmentData.content)
      filename = attachment["filename"]


      #handle doc
      if os.path.splitext(filename)[1] == ".docx" or os.path.splitext(filename)[1] == ".zip":
        doc = docx.Document(filename)
        with open(filename, 'rb') as f:
          zip = zipfile.ZipFile(f)

          for info in zip.infolist():
            is_image = ("jpg" in info.filename or "png" in info.filename or "jpeg" in info.filename)
            if is_image:
              pic_path = zip.extract(info, f"/{user['name']}{user['id']}profile{os.path.splitext(info.filename)[1]}")

        for para in doc.paragraphs:
          if len(para.text) > 10:
            bio = bio + (f"<p>{para.text}</p>\n")

      #if it's an attached image
      elif os.path.splitext(filename)[1] in ['.jpg', '.jpeg', '.png']:
        with open(f"{user['name']}{user['id']}profile{os.path.splitext(filename)[1]}", "wb") as f:
          f.write(attachmentData.content)
          pic_path = os.path.realpath(f.name)

    #todo: upload resized profile pic and populate upload_url
  img_upload_url = ""
  if len(pic_path) > 0:
    pic_path = resize_image(pic_path, max_profile_image_size)
    img_upload_url = upload_image(pic_path, instructor_course_id)

  img_src = img_upload_url if len(img_upload_url) > 0 else default_profile_url

  return dict(user = user, bio = bio, img_src = img_src, local_image_path = pic_path)

#TODO write this in
def resize_image(path, max_width):
    input_path = path
    output_path = path
    with Image.open(input_path) as img:
        print (img.size)
        if max_width >= img.size[0]:
          print (max_width, img.size)
          return input_path

        target_width = max_width

        # Calculate the new height to preserve the aspect ratio
        width_percent = (target_width / float(img.size[0]))
        new_height = int((float(img.size[1]) * float(width_percent)))

        # Resize the image using the appropriate resampling filter
        resized_img = img.resize((target_width, new_height), Image.Resampling.BILINEAR)

        # Save the resized image
        resized_img.save(output_path)
        log(output_path)
    return output_path

#TODO: write this in
def upload_image(pic_path, course_id):
  return ""

def get_instructor_page(user):
    url = f"{api_url}/courses/{profile_pages_course_id}/pages?per_page=999&search={urllib.parse.quote(user['name'])}" 
    response = requests.get(url, headers=headers) 
    if response.status_code != 200:
      return None
    pages = response.json()

    pagination_links = response.headers["Link"].split(",")
    next_page_link = pagination_links[1].split(";")[0].split("<")[1].split(">")[0]
    firstTime = True
    while len(pagination_links)  > 4 or firstTime:
        firstTime = False
        log(len(pagination_links))
        # Make a request to the next page
        response = requests.get(next_page_link, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:

            # Iterate over the results on the next page
            for page in response.json():
                pages.append(page)

            # Get the next page link from the response headers
            pagination_links = response.headers["Link"].split(",")
            log(pagination_links)
            next_page_link = pagination_links[1].split(";")[0].split("<")[1].split(">")[0]
            log(next_page_link)

    for page in pages:
      log(page["title"])


def get_canvas_course_home_page(course_id):
  # Make the request to the Canvas LMS course home page.
  url = f"https://unity.instructure.com/courses/{course_id}"
  response = requests.get(url, headers=headers)
  return response.content

def get_canvas_instructor(course_id):
  url = "{}/courses/{}/users?enrollment_type=teacher".format(api_url, course_id)
  response = requests.get(url, headers=headers)
  if response.status_code != 200:
    return None

  users = response.json()
  for user in users:
    return user

  return None

def get_paged_data(url, headers=headers):
  response = requests.get(url, headers=headers)
  out = response.json()
  next_page_link = "!"
  while len(next_page_link) != 0:
      pagination_links = response.headers["Link"].split(",")
      for link in pagination_links:
        if 'next' in link:
          next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
          log(next_page_link)
          response = requests.get(next_page_link, headers=headers)
          out = out + response.json()
          break
        else:
          next_page_link = ""  
  log(len(out))

  return out
main()