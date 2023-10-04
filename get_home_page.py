from bs4 import BeautifulSoup
import docx
import sys
import requests
import urllib.parse
import zipfile
import os
import PyPDF2
import json

api_url = "https://unity.test.instructure.com/api/v1"

CONSTANTS_FILE = 'constants.json'

# Open the file and read the contents
with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)

# Print the API key
apiToken = constants["testApiToken"]

instructor_course_id = constants["instructorCourseId"]
profile_assignment_id = constants["profileAssignmentId"] 
profile_pages_course_id = constants["profilePagesCourseId"]

bp_id = sys.argv[1] #3848068


# Authorize the request.
headers = {"Authorization": f"Bearer {apiToken}"}

def main():
  pages = get_faculty_pages()
  courses = get_blueprint_courses(bp_id)
  profiles = []
  i = 1
  for course in courses:
    profile = get_course_profile(course, pages)
    profiles.append(profile)
    format_profile_page(profile,course)
    overwrite_home_page(profile, course)
    print(f"processed {i} of {len(courses)}")
    i = i + 1

  for profile in profiles:
    if len(profile["bio"]) >= 5:
      print(f'{profile["user"]["name"]} does have a bio we can find')

  for profile in profiles:
    if len(profile["bio"]) < 5:
      print(f'{profile["user"]["name"]} does NOT have a bio we can find')
      print(profile)

   

def get_paged_data(url):
  response = requests.get(url, headers=headers)
  out = []
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

def save_bios(bios, path="bios.json"):
  with open(path, 'w') as f:
    json.dump(bios, f)

def get_faculty_pages():
  if os.path.isfile("bios.json"):
    with open("bios.json", 'r') as f:
      pages = json.load(f)
      print(len(pages))
  else:
    pages = get_paged_data(f"{api_url}/courses/{profile_pages_course_id}/pages?include=body")
    save_bios(pages)    
  return pages

def format_profile_page(profile, course):
  with open("template.html", 'r') as f:
    template = f.read()
  text = template.format(course_title = course["name"], instructor_name = profile["user"]["name"], img_src = profile["img_src"], bio=profile["bio"])
  with open(f'profiles/{profile["user"]["id"]}_{course["id"]}.htm', 'w') as f:
    f.write(text)
  return text

def get_course_profile(course, pages):
  return get_course_profile_from_pages(course, pages)
  


def get_course_profile_from_pages(course, pages):
  instructor = get_canvas_instructor(course["id"])
  course_id = course["id"]

  profile = get_instructor_profile_from_pages(instructor, pages)
  #this does not fully format the bio present yet so leaving it off for now
  #if len(profile["bio"]) == 0:
  #  profile = get_instructor_profile_submission(instructor)
  return profile


def get_course_profile_from_assignment(course):
  instructor = get_canvas_instructor(course["id"])
  course_id = course["id"]
  if instructor is not None:
    print("The instructor of the course {} is {}".format(course_id, instructor))
  else:
    print("The instructor of the course {} cannot be found.".format(course_id))
  return get_instructor_profile_submission(instructor)


def get_blueprint_courses(bp_id):
  url = f"{api_url}/courses/{bp_id}/blueprint_templates/default/associated_courses"
  response = requests.get(url, headers=headers)
  courses = response.json()
  next_page_link  = "!"
  while len(next_page_link) != 0:
    pagination_links = response.headers["Link"].split(",")
    for link in pagination_links:
      if 'next' in link:
        next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
        response = requests.get(next_page_link, headers=headers)
        courses = courses + response.json()
        print("added courses at", next_page_link )
        break
      else:
        next_page_link = ""
      print(link)


  return courses

def overwrite_home_page(profile, course):
  # Make a GET request to the Canvas LMS API to get the homepage of the course.
  url = f'{api_url}/courses/{course["id"]}/front_page'
  print(url)
  response = requests.get(url, headers=headers)

  # Check the response status code.
  if response.status_code != 200:
    raise ValueError('Failed to get homepage of course: {}'.format(response.status_code))

  # Get the homepage HTML content.
  
  homepage_html = response.json()['body']
  data = {'wiki_page[body]': format_profile_page(profile, course)}
  response = requests.put(url, headers=headers, data=data)
  print(response)



def get_instructor_profile_from_pages(user, pages):
  first_name = user["name"].split(" ")[0]
  last_name = user["name"].split(" ")[-1]

  def restrictive_filter_func(entry):
    return user["name"].lower() in entry["title"].lower()
  def premissive_filter_func(entry):
    return last_name.lower() in entry["title"].lower() and first_name.lower() in entry["title"].lower()

  potentials = list(filter(restrictive_filter_func, pages))
  if len(potentials) == 0:
    potentials = list(filter(premissive_filter_func, pages))

  out = dict( user=user, bio = "", img = "", img_src = "")
  if len(potentials) > 1:
    print(potentials)
    return out
  for potential in potentials:
    if not "body" in potential:
      continue
    html = potential["body"]
    soup = BeautifulSoup(html, 'html.parser')

    h4_tags = soup.find_all('h4')

    # Iterate over the h4 tags and find the next sibling paragraph tag
    paragraphs = []
    bio = ""
    for h4_tag in h4_tags:
        next_sibling = h4_tag.find_next_sibling('p')
        if next_sibling is not None:
            paragraphs.append(next_sibling.text)

    # Print the paragraphs
    for paragraph in paragraphs:
        bio = f"{bio}\n<p>{paragraph}</p>"


    out["bio"] = bio
    imgs = soup.find_all("img")
    for img in imgs:
      out["img"] = img["src"]
      out["img_src"] = img["src"]
  return out


def get_instructor_profile_submission(user):
  url = f"{api_url}/courses/{instructor_course_id}/assignments/{profile_assignment_id}/submissions/{user['id']}"
  response = requests.get(url, headers=headers)
  submission = response.json()
  print(submission)
  bio = submission["body"] and submission["body"] or ""
  pic_path = ""
  if "attachments" in submission:
    for attachment in submission["attachments"]:
      url = attachment["url"]
      attachmentData = requests.get(url, headers=headers)

      with open (attachment["filename"], 'wb') as f:
        f.write(attachmentData.content)
      filename = attachment["filename"]


      #handle doc
      if os.path.splitext(filename)[1] == ".docx" or os.path.splitext(filename)[1] == ".zip":
        doc = docx.Document(attachment["filename"])
        with open(attachment["filename"], 'rb') as f:
          zip = zipfile.ZipFile(f)

          for info in zip.infolist():
            is_image = ("jpg" in info.filename or "png" in info.filename or "jpeg" in info.filename)
            if is_image:
              pic_path = zip.extract(info, f"/{user['id']}profile{os.path.splitext(info.filename)[1]}")

        for para in doc.paragraphs:
          if len(para.text) > 20:
            bio = bio + (f"<p>{para.text}</p>\n")

      #if it's an attached image
      elif os.path.splitext(filename)[1] in ['.jpg', '.jpeg', '.png']:
        pic_path = open(f"{user['id']}profile{os.path.splitext(filename)[1]}", "wb").write(attachmentData.content)


  return dict(user = user, bio = bio, img = pic_path)


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
        print(len(pagination_links))
        # Make a request to the next page
        response = requests.get(next_page_link, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:

            # Iterate over the results on the next page
            for page in response.json():
                pages.append(page)

            # Get the next page link from the response headers
            pagination_links = response.headers["Link"].split(",")
            print(pagination_links)
            next_page_link = pagination_links[1].split(";")[0].split("<")[1].split(">")[0]
            print(next_page_link)

    for page in pages:
      print(page["title"])


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
main()