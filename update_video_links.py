from pathlib import Path
from PIL import Image
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

ADD_LEARNING_MATERIALS = False
UPDATE_SYLLABUS = True
CONSTANTS_FILE = "constants.json"




# Open the file and read the contents
try:
  with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)
except Exception as e:
  tk.messagebox.showerror(message=f"Problem loading constants.json. Ask hallie for a copy of constants.json and put it in this folder.\n{e}")
# save the api key
try:
  api_token = constants["apiToken"]
  api_url = constants["apiUrl"]
  html_url = re.sub('\/api\/v1', '', api_url)
  drive_url = None
  if "driveUrl" in constants:
    drive_url = constants["driveUrl"]

  account_id = 169877
except Exception as e:
  print(e)
  tk.messagebox.showerror(message=f"It looks like your constants file is missing some values. Ask hallie for a current copy of the constants.json file.\n{e}")


# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}" }

def main():
  course_id = 0
  old_course_id = 0

  if len(sys.argv) > 1:
   course_id = sys.argv[1]
  else:
   course_id = str(tk.simpledialog.askinteger("What Course?", "Enter the course_id of the new course (cut the number out of the url and paste here)"))


  url = f"{api_url}/courses/{course_id}"
  print(url)
  response = requests.get(url, headers=headers)
  print(response)
  if response.status_code != 200:
    tk.messagebox.showinfo("report", f"Course not found.\n{response.text}")
    exit()
  course = response.json()

  if not old_course_id or old_course_id == 0:
    code = course["course_code"].split("_")[1][0:7]
    print("Code", code)
    response = requests.get(f"{api_url}/accounts/{account_id}/courses", headers=headers, params = {"search_term" : f"DEV_{code}"} )
    courses = response.json()

    for course in courses:
      print(course["course_code"])
    if len(courses) > 0:
      old_course_id = courses[0]["id"]
      print("Old course found", old_course_id, courses[0]["course_code"])


  old_modules = get_modules(old_course_id)
  modules = get_modules(course_id)



  if len(sys.argv) > 2:
    if "syllabus" in sys.argv:
      update_syllabus_and_overview(course_id, old_course_id)
    if "overviews" in sys.argv:
      update_weekly_overviews(course_id, old_course_id)
    if "assignments" in sys.argv:
      assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
      align_assignments(course_id, old_course_id, assignments_lut)
    if "rubrics" in sys.argv:
      assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
      align_rubrics(course_id, old_course_id, assignments_lut)
    if  "lm" in sys.argv:
      assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
      files_lut = get_file_lookup_table(course_id, old_course_id)
      update_learning_materials(course_id, old_course_id, files_lut, assignments_lut)
    if  "delete" in sys.argv:
      remove_assignments_and_discussions_not_in_modules(course_id)
    if "hometiles" in sys.argv:
      set_hometiles(course_id)


  else:
    if tk.messagebox.askyesno(message="Do you want to update the syllabus and course overview?"):
      try:
        update_syllabus_and_overview(course_id, old_course_id) 
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem updating the syllabus and overviews\n{e}")

    if tk.messagebox.askyesno(message="Do you want to try to update the weekly overviews?"):
      try:
        update_weekly_overviews(course_id, old_course_id)       
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem updating weekly overviews\n{e}")

    if tk.messagebox.askyesno(message="Do you want to update assignments?"):
      try:
        assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
        align_assignments(course_id, old_course_id, assignments_lut)
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem updating assignments\n{e}")

    if tk.messagebox.askyesno(message="Do you want to update learning materials?\nNOTE: this will also create missing assignments, discussions, if they don't exist so links can be migrated"):
      try:
        assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
        files_lut = get_file_lookup_table(course_id, old_course_id)        
        update_learning_materials(course_id, old_course_id, files_lut, assignments_lut)
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem updating learning materials\n{e}")

    if tk.messagebox.askyesno(message="Do you want to update rubrics?"):
      try:
        assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
        align_rubrics(course_id, old_course_id, assignments_lut)
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem updating rubrics\n{e}")

    if tk.messagebox.askyesno(message="Do you want to try to delete assignments no in discussions and modules?\nYou will see a list of items to confirm."):
      try:
        remove_assignments_and_discussions_not_in_modules(course_id)
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem deleting assigments and or discussions\n{e}")        

    if tk.messagebox.askyesno(message="Do you want to automatically make hometiles based on overview banners?"):
      try:
        set_hometiles(course_id)
      except Exception as e:
        tk.messagebox.showerror(message=f"there was a problem creating hometiles\n{e}")        
  
    tk.messagebox.showinfo(message="Finished!")


def set_hometiles(course_id):

  url = f"{api_url}/courses/{course_id}/pages/home"
  response = requests.get(url, headers=headers)

  page = response.json()
  soup = BeautifulSoup(page["body"], 'lxml')


  banner = soup.find("div", class_="cbt-banner-image").find('img')
  src = banner['src']
  response = requests.get(src)
  img_data = response.content
  ext = "png" if 'png' in response.headers["Content-Type"] else 'jpg'

  cwd = os.getcwd()
  path = os.path.join(cwd, "images")
  if not os.path.exists(path):
    os.mkdir(path)
  path = os.path.join(path, f"{course_id}")
  if not os.path.exists(path):
    os.mkdir(path)

  filepath = save_hometile(img_data, filepath = os.path.join(path, f"hometile1.{ext}"))
  upload_hometile(course_id, filepath)

  i = 1
  modules = get_modules(course_id)
  for module in modules:
    url = f"{api_url}/courses/{course_id}/pages/week_{i}_overview"
    response = requests.get(url, headers=headers)
    if not response.ok: #quit if we can't find the page
      print(response)
      return

    page = response.json()
    soup = BeautifulSoup(page["body"], 'lxml')

    banner = soup.find("div", class_="cbt-banner-image").find('img')
    src = banner['src']
    response = requests.get(src)
    img_data = response.content
    ext = "png" if 'png' in response.headers["Content-Type"] else 'jpg'

    cwd = os.getcwd()
    path = os.path.join(cwd, "images", str(course_id))

    home_tile_path = save_hometile(img_data, filepath = os.path.join(path, f"hometile{i + 1}.{ext}"))
    upload_hometile(course_id, home_tile_path)
    i = i + 1

def upload_hometile(course_id, local_path):
  #get the correct folder in this 
  

  url = f"{api_url}/courses/{course_id}/folders/by_path/Images/hometile"
  response = requests.get(url, headers=headers)
  folders = response.json()
  hometile_folder = folders[-1]
  file_url = f"{api_url}/courses/{course_id}/files"
  print(f"uploading {local_path} to {file_url}")
  data = {
    "name" : os.path.basename(local_path),
    "no_redirect" : True,
    "parent_folder_id" : hometile_folder["id"],
    "on_duplicate" : "overwrite"
  }

  print(data)
  response = requests.post(file_url, data=data, headers=headers)
  print(response)
  print(response.reason)
  if response.ok:
    response_data = response.json()
    files = { "file" : open(local_path, 'rb')}
    url = response_data["upload_url"]
    response = requests.post(url, files=files, data=response_data['upload_params'])
    print(response)
    if not response.ok:
      print(response.text)
      return False

    if response.is_redirect:
      requests.Session().send(response.next)



def save_hometile(img_data, filepath):
  print(filepath)
  HOMETILE_WIDTH = 512
  with open(filepath, 'wb') as file:
    file.write(img_data)

  with Image.open(filepath) as img:
    if HOMETILE_WIDTH >= img.size[0]:
      print (HOMETILE_WIDTH, img.size)
    else:
      target_width = HOMETILE_WIDTH

      # Calculate the new height to preserve the aspect ratio
      width_percent = (target_width / float(img.size[0]))
      new_height = int((float(img.size[1]) * float(width_percent)))

      # Resize the image using the appropriate resampling filter
      resized_img = img.resize((target_width, new_height), Image.Resampling.BILINEAR)

      pre, ext = os.path.splitext(filepath)
      # Save the resized image
      home_tile_path = f"{pre}.png"
      resized_img.save(home_tile_path,"PNG")

      return home_tile_path


def get_modules(course_id):
  url = f"{api_url}/courses/{course_id}/modules?include[]=items&include[]=content_details"
  response = requests.get(url, headers=headers)
  return response.json()
  
def create_missing_assignments(modules, old_modules, course_id, old_course_id):
  print("Creating missing assignments")
  modules = get_modules(course_id)
  old_modules = get_modules(old_course_id)

  handled = []

  for old_module in old_modules:
    items = old_module["items"]
    #skip non-week modules
    number = get_old_module_number(old_module)
    name = get_old_module_title(old_module)
    if not number:
      continue

    module = find_new_module_by_number(number, modules)

    #save off the gallery discussion
    if number == "1":
      gallery_search = filter( lambda item: "Gallery Discussion" in item["title"], module["items"])
      gallery_discussion_template = next( filter( lambda item: "Gallery Discussion" in item["title"], module["items"]), None)

    create_missing_assignments_in_module(module, old_module, course_id, old_course_id, gallery_discussion_template)
    handled.append(module)

  #remove named modules that were not handled
  to_remove = list( filter( lambda module: (not module in handled) and "Module" in module["name"], modules))
  module_name_list = "\n".join(list( map(lambda module: module["name"], to_remove)))
  if len(to_remove) and tk.messagebox.askyesno(message=f"Do you want to remove the following modules and their contents?\n{module_name_list}"):
    for module in to_remove:
      remove_module(course_id, module, True)


def remove_module(course_id, module, delete_contents):
  if delete_contents:
    for item in module["items"]:
      url = item["url"]
      print(f"Deleting {url}")
      result = requests.delete(url, headers=headers)

  url = f"{api_url}/courses/{course_id}/modules/{module['id']}"
  result = requests.delete(url, headers=headers)


def create_missing_assignments_in_module(module, old_module, course_id, old_course_id, gallery_discussion_template):
  add_quizzes(module, old_module, course_id, old_course_id)
  add_assignments(module, old_module, course_id, old_course_id)
  add_discussions(module, old_module, course_id, old_course_id, gallery_discussion_template)

def add_quizzes(module, old_module, course_id, old_course_id):
  old_quizzes = list ( filter( lambda item: item["type"] == "Quiz", old_module["items"]) )
  quizzes = list( filter( lambda item: item["type"] == "Quiz", module["items"]) )

  difference = len(old_quizzes) - len(quizzes)

  if difference > 0:
  #we're looking for imported quizzes now

    url = f"{api_url}/courses/{course_id}/quizzes"
    all_quizzes_in_course = get_paged_data(url)
    for old_quiz in old_quizzes:
      #if the quiz is there, we're good
      if next(filter(lambda item: item["title"] == old_quiz["title"], quizzes), None):
        continue
      else:
        print("Adding Quiz To Module")
        new_quiz = next( filter(lambda item: item["title"] == old_quiz["title"], all_quizzes_in_course), None)
        assert new_quiz, f"Quiz not found:{old_quiz['title']}"
        url = f"{api_url}/courses/{course_id}/modules/{module['id']}/items"
        result = requests.post(url, headers=headers, data={
          "module_item[type]" : "Quiz",
          "module_item[content_id]" : new_quiz["id"],
          "module_item[completion_requirement][type]" : "must_submit" ,
          "module_item[indent]" : 1,
          "module_item[position]" : 999
          })


def add_assignments(module, old_module, course_id, old_course_id):
  old_assignments = list ( filter( lambda item: item["type"] == "Assignment", old_module["items"]) )
  assignments = list( filter( lambda item: item["type"] == "Assignment", module["items"]) )
  difference = len(old_assignments)  - len(assignments)
  if difference > 0:
    added_items = True

    #duplicate the first assignment as many times as it takes to get parity between assignments
    for _ in range(0, difference):
      duplicate_item(course_id, assignments[0], module)

def add_discussions(module, old_module, course_id, old_course_id, gallery_discussion_template):
  #get discussions and pull out gallery discussions to handle differently
  old_discussions = list ( filter( lambda item: item["type"] == "Discussion", old_module["items"]) )
  old_gallery_discussions = remove_gallery_discussions(old_discussions)
  print("---------------------------------------")
  print(old_discussions)
  print("---------------------------------------")
  print(old_gallery_discussions)
  print("---------------------------------------")

  discussions = list( filter( lambda item: item["type"] == "Discussion", module["items"]) )
  gallery_discussions = remove_gallery_discussions(discussions)


  #if we don't have a gallery discussion template, just duplicate the first discussion
  if not gallery_discussion_template:
    gallery_discussion_template = discussions[0]

  #add discussions if there is disparity
  difference = len(old_discussions)  - len(discussions)
  if difference > 0:
    added_items = True

    #duplicate the first discussion as many times as it takes to get parity between discussions
    for _ in range(0, difference):
      duplicate_item(course_id, discussions[0], module)

  difference = len(old_gallery_discussions)  - len(gallery_discussions)
  if difference > 0:
    added_items = True

    #duplicate the gallery discussion template as many times as it takes to get parity between gallery discussions
    for _ in range(0, difference):
      duplicate_item(course_id, gallery_discussion_template, module)




files_lut_cache = None
def get_file_lookup_table(course_id, old_course_id):
  global files_lut_cache
  if files_lut_cache:
    return files_lut_cache

  files = get_paged_data(f"{api_url}/courses/{course_id}/files?per_page=100")
  old_files = get_paged_data(f"{api_url}/courses/{old_course_id}/files?per_page=100")


  old_file_url_lookup_table = dict()
  for old_file in old_files:
    #match files by name and size
    file = list( filter( lambda a: old_file["filename"] == a["filename"], files) )[0]
    old_file_url_lookup_table[str(old_file["id"])] = file

  files_lut_cache = old_file_url_lookup_table
  return old_file_url_lookup_table  


assignments_lut_cache = None
def get_assignments_lookup_table(modules, old_modules, course_id, old_course_id, force=False):
  global assignments_lut_cache
  if assignments_lut_cache and not force:
    return assignments_lut_cache

  #we have to create missing assignments as part of getting assignments lookup table
  create_missing_assignments(modules, old_modules, course_id, old_course_id)

  assignments_lut = dict()

  #build assignments from modules by getting assignments in order, discussions in order, and gallery discussion in order

  old_modules = get_modules(old_course_id)
  modules = get_modules(course_id)

  for old_module in old_modules:
    items = old_module["items"]

    #skip non-week modules
    number = get_old_module_number(old_module)
    name = get_old_module_title(old_module)
    if not number:
      continue

    module = find_new_module_by_number(number, modules)
  
    old_assignments = list ( filter( lambda item: item["type"] == "Assignment", old_module["items"]) )
    assignments = list( filter( lambda item: item["type"] == "Assignment", module["items"]) )
  
    discussions = list( filter( lambda item: item["type"] == "Discussion", module["items"]) )
    old_discussions = list ( filter( lambda item: item["type"] == "Discussion", old_module["items"]) )
  
    old_gallery_discussions = remove_gallery_discussions(old_discussions)
    gallery_discussions = remove_gallery_discussions(discussions)

    populate_lookup_table(assignments_lut, assignments, old_assignments)
    populate_lookup_table(assignments_lut, discussions, old_discussions)
    populate_lookup_table(assignments_lut, gallery_discussions, old_gallery_discussions)


  #We also want to associate discussions with their corresponding assignment ID
  discussions = get_paged_data(f"{api_url}/courses/{course_id}/discussion_topics")
  old_discussions = get_paged_data(f"{api_url}/courses/{old_course_id}/discussion_topics")

  discussions_by_ids = dict()
  for discussion in discussions:
    discussions_by_ids[discussion['id'] ] = discussion

  for old_discussion in old_discussions: 
    if not str(old_discussion['id']) in assignments_lut:
      print (f"Skipping {old_discussion['title']}")
      continue

    discussion_info = assignments_lut[ str(old_discussion['id']) ]
    discussion_id = discussion_info['content_id']
    print(f"looking for discussion {discussion_id}")
    discussion = discussions_by_ids[ discussion_id ]
    print(old_discussion['assignment_id'])
    assignments_lut[ str(old_discussion['assignment_id']) ] = discussion


  assignments_lut_cache = assignments_lut
  return assignments_lut

def get_rubrics_lookup_table(rubrics, old_rubrics ):
  out = dict()
  for old_rubric in old_rubrics:
    print(old_rubric["title"])
    rubric = next( filter( lambda a: a["title"] == old_rubric["title"], rubrics) ) 
    print(rubric["title"])
    out[ old_rubric["id"] ] = rubric

  return out

def align_rubrics(course_id, old_course_id, assignments_lut):

  old_rubric_url = f"{api_url}/courses/{old_course_id}/rubrics?per_page=100"
  rubric_url = f"{api_url}/courses/{course_id}/rubrics?per_page=100"

  old_rubric_response = requests.post(old_rubric_url, headers=headers)
  rubric_response = requests.post(rubric_url, headers=headers)


  old_rubrics = get_paged_data(old_rubric_url)
  rubrics = get_paged_data(rubric_url)

  rubrics_lut = get_rubrics_lookup_table(rubrics, old_rubrics)
  for old_rubric in old_rubrics:
    try:

      response = requests.get(f"{api_url}/courses/{old_course_id}/rubrics/{old_rubric['id']}", headers=headers, data={ "include[]" : "associations"} )
      assert response.ok, f"problem getting rubric {old_rubric['id']} : {old_rubric['description']}"
      old_rubric_data = response.json()
      for association in old_rubric_data["associations"]:
        old_item_id = association["association_id"]
        print(old_item_id)
        if association["association_type"] == "Assignment":
          print(assignments_lut.keys())
          rubric = rubrics_lut[ old_rubric["id"] ]
          print("assigning...")
          assignment = assignments_lut[str(old_item_id)]
          assignment_id = ""
          if "content_id" in assignment:
            assignment_id = assignment["content_id"]
          else:
            assignment_id = assignment["assignment"]["id"]

          payload = {
            "rubric_association[association_id]" : assignment_id, 
            "rubric_association[rubric_id]" : rubric["id"],
            "rubric_association[association_type]" : "Assignment",
            "rubric_association[purpose]": "grading",
            "rubric_association[use_for_grading]" : True,
          }


          site_url = re.sub(r"/api/v1", "", api_url)
          url = f"{api_url}/courses/{course_id}/rubric_associations"
          response = requests.post(url, headers=headers, data = payload)
          print(response)

          assert response.ok
          url = f"{api_url}/courses/{course_id}/rubrics/{rubric['id']}"



    except Exception as e:
      print("---ERROR---")
      print(f"Problem with {old_rubric['id']}...")
      print(type(e))
      print(e.args)
      raise e
      print("---/ERROR---")



def align_assignments(course_id, old_course_id, assignments_lut):
  modules = get_modules(course_id)
  old_modules = get_modules(old_course_id)
  old_id_to_id_lut = dict()

  files_lut = get_file_lookup_table(course_id, old_course_id)


  for old_module in old_modules:
    items = old_module["items"]

    #skip non-week modules
    number = get_old_module_number(old_module)
    name = get_old_module_title(old_module)
    if not number:
      continue

    module = find_new_module_by_number(number, modules)
  
    old_assignments = list ( filter( lambda item: item["type"] == "Assignment", old_module["items"]) )
    assignments = list( filter( lambda item: item["type"] == "Assignment", module["items"]) )
  
    old_discussions = list ( filter( lambda item: item["type"] == "Discussion", old_module["items"]) )
    old_gallery_discussions = remove_gallery_discussions(old_discussions)

    discussions = list( filter( lambda item: item["type"] == "Discussion", module["items"]) )
    gallery_discussions = remove_gallery_discussions(discussions)

    discussion_number = 1
    gallery_discussion_number = 1
    assignment_number = 1


    ctx = {
        "files_lut" : files_lut,
        "assignments_lut" : assignments_lut,
        "course_id" : course_id,
        "old_course_id" : old_course_id,
    }

    handle_items(course_id, old_course_id, module, gallery_discussions, old_gallery_discussions, handle_discussion, f"Week {number} " +  "Gallery Discussion {number}- {name}", ctx)
    handle_items(course_id, old_course_id, module, discussions, old_discussions, handle_discussion, f"Week {number} " + "Discussion {number}- {name}", ctx)
    handle_items(course_id, old_course_id, module, assignments, old_assignments, handle_assignment, f"Week {number} " + "Assignment {number}- {name}", ctx)

#look through img and a tags. Replace src and href tags if they point to a file we know about. 
#assignments coming

def get_new_file_url(src, ctx):
  files_lut = get_file_lookup_table(ctx["course_id"], ctx["old_course_id"])
  course_id = ctx["course_id"]
  old_course_id = ctx["old_course_id"]
  file_match = re.search(r"files\/([0-9]+)", src)
  if file_match:
    groups = file_match.groups()
    old_id = groups[0]
    if old_id in files_lut:
      new_file = files_lut[old_id]
      #url = re.sub(str(old_course_id), str(course_id), src)
      #url = re.sub(str(old_id), str(new_file['id']), src)
      url = new_file['url']
      url = re.sub('verifier(.*)&?', '', url)  
      if "wrap" in src:
        url = url + "wrap=1"
      #url = f"{html_url}/courses/{course_id}/files/{new_file['id']}"
      data_url = re.sub(html_url, api_url, new_file['url'])
      return url, data_url

  return None, None


def get_new_assignment_url(src, ctx):
  assignments_lut = ctx["assignments_lut"]

  course_id = ctx["course_id"]
  file_match = re.search(r"(assignments|discussion_topics)\/([0-9]+)", src)
  if file_match:
    type_url_part = file_match.groups()[0]
    print(type_url_part)
    groups = file_match.groups()
    old_id = groups[1]
    if str(old_id) in assignments_lut:
      new_assignment = assignments_lut[str(old_id)]
      print(new_assignment)
      content_id = None
      if 'content_id' in new_assignment:
        content_id = new_assignment['content_id']
      else:
        content_id = new_assignment['id']
      url = f"{html_url}/courses/{course_id}/{type_url_part}/{content_id}"
      data_url = url

      return url, data_url

  return None, None

def get_new_page_url(src, ctx):
  #naively update link by keeping same path and updating course if
  page_match = re.search(fr"courses\/{ctx['old_course_id']}/pages\/(.+)", src)
  print(f"Remapping page {src}")
  if page_match:
    groups = page_match.groups()
    path = groups[0]
    url = re.sub(f'/courses/.*', f'/courses/{ctx["course_id"]}/pages/{path}', src)
    data_url = re.sub('/api/v1', '', url)
    return url, data_url
  return None, None

def update_links(soup, ctx):
  course_id = ctx["course_id"]
  old_course_id = ctx["old_course_id"]

  modules = get_modules(course_id)
  old_modules = get_modules(old_course_id)

  files_lut = get_file_lookup_table(course_id, old_course_id)
  assignments_lut = get_assignments_lookup_table(modules, old_modules, course_id, old_course_id)
  print("Updating Links")
  #handle a tags
  links = soup.find_all('a')
  for link in links:
    if not link.has_attr('href'):
      print("No Href in Link")
      print(link)
      continue

    #skip outside links
    if not "instructure" in link['href']: 
      continue

    print(link['href'])

    #see if we can turn it into a new page, file, or assignment url
    for func in [get_new_file_url, get_new_assignment_url, get_new_page_url]:
      new_url, data_url = func(link["href"], ctx)
      if new_url:
        old_url = link['href']
        link["href"] = new_url
        link["data_api_endpoint"] = data_url
        print(f'{old_url}\nmapped to\n{link["href"]}')
        break

  #handle images
  imgs = soup.find_all('img')
  for img in imgs:
    if not img.has_attr('src'):
      continue
    if not 'instructure' in img['src']:
      continue
    new_url, data_url = get_new_file_url(img["src"], ctx)
    
    if new_url:
      old_url = img['src']
      img["src"] = new_url
      img["data_api_endpoint"] = data_url
      print(old_url + " ---> " + img["src"])


def handle_items(course_id, old_course_id, module, items, old_items, handle_func, format_title, ctx):
  i = 0

  handled = []

  for old_item in old_items:
    item = items[i]
    handled.append(item)
    course_id_regex = re.compile(f'{api_url}/courses/(\d+)/(assignments|discussion_topics)/(\d+)')
    match = course_id_regex.match(items[0]["url"])
    old_match = course_id_regex.match(old_item["url"])


    print(f"Parsing {old_item['title']} into {item['title']}")


    assert match, f"regex broken for string {items[0]['url']}"
    assert old_match, f"regex broken for string {old_item['url']}"
    item_id = match.group(3)
    old_item_id = old_match.group(1)

    url = item["url"]
    old_url = old_item["url"]
    response = requests.get(url, headers=headers)
    assert response.ok, json.dumps(response.json(), indent=2)

    old_response = requests.get(old_url, headers=headers)
    assert old_response.ok, json.dumps(response.json(), indent=2)

    item = response.json()
    old_item = old_response.json()

    handle_func(item, old_item, url, i, len(old_items), format_title, ctx)
    i = i + 1

  for item in items:
    if not item in handled:
      remove_item_from_module(item, module, course_id)

def remove_item_from_module(item, module, course_id):
  print(json.dumps(item, indent=2))
  url = f"{api_url}/courses/{course_id}/modules/{item['module_id']}/items/{item['id']}"
  print(url)
  response = requests.delete(url, headers=headers)
  print("DELETING")
  print(response.json())

def handle_discussion(item, old_item, put_url, index, total, format_title, ctx):

  files_lut  = ctx["files_lut"]
  assignments_lut = ctx["assignments_lut"]

  old_name = old_item["title"]
  name = item["title"]

  display_number = ""
  if total > 1:
    display_number = f"{index + 1} "

  title = re.sub(r'^.*[:-]\W+', '', old_name)
  new_name = format_title.format(number=display_number, name=title)
  subhead = re.sub(r'[:-].*', '', new_name)
  print(f"migrating {old_name} to {new_name}")
  old_body = old_item["message"]
  body = item["message"]

  old_soup = BeautifulSoup(old_body, 'lxml')
  soup = BeautifulSoup(body, 'lxml')

  contents = old_soup.find('div', class_="column")

  insert_el = soup.find('div', id="migrate_insert")
  if not insert_el:
    insert_el = soup.new_tag('div', id="migrate_insert")
    soup.body.insert(len(soup.body.contents), insert_el)

  #replace_header
  head = soup.h1
  head.string.replace_with(title)

  subhead_el = soup.find('h1').find_previous_sibling('p')
  subhead_el.string.replace_with(subhead)


  if contents:
    insert_el.clear()
    insert_el.append(contents)

  update_links(soup, ctx)

  response = requests.put(put_url, headers=headers, data= {
    "title" : new_name,
    "message" : soup.prettify()
    })


def handle_assignment(item, old_item, put_url, index, total, format_title, ctx):

  files_lut  = ctx["files_lut"]
  assignments_lut = ctx["assignments_lut"]


  old_name = old_item["name"]
  name = item["name"]

  display_number = ""
  if total > 1:
    display_number = f"{index + 1} "

  title = re.sub(r'^.*[:-]\W+', '', old_name)
  new_name = format_title.format(number=display_number, name=title)
  subhead = re.sub(r'[:-].*', '', new_name)
  print(f"migrating {old_name} to {new_name}")

  old_body = old_item["description"]
  old_soup = BeautifulSoup(old_body, 'lxml')
  body = item["description"]
  soup = BeautifulSoup(body, 'lxml')

  head = soup.h1
  head.string.replace_with(title)

  subhead_el = soup.find('h1').find_previous_sibling('p')
  subhead_el.string.replace_with(subhead)

  #insert the contents of the old page into the bottom of the new page
  contents = old_soup.find('div', class_="column")
  if not contents:
    contents = old_soup.body

  insert_el = soup.find('div', id="migrate_insert")
  if not insert_el:
    insert_el = soup.new_tag('div', id="migrate_insert")
    soup.body.insert(len(soup.body.contents), insert_el)

  insert_el.clear()
  if contents:
      insert_el.append(contents)

  #update links on the whole thing
  update_links(soup, ctx)

  new_text = soup.prettify()

  response = requests.put(put_url, headers=headers, data= {
    "assignment[name]" : new_name,
    "assignment[description]" : new_text
    })

def populate_lookup_table(lut, items, old_items):
  i = 0
  if len(old_items) > len(items):
    raise Exception("Number of items in new module is fewer than items in old module")
  for old_item in old_items:
    print(old_item)
    item = items[i]
    i = i + 1
    lut[str(old_item["content_id"]) ] = item

def remove_assignments_and_discussions_not_in_modules(course_id):
  modules = get_modules(course_id)
  discussions_in_modules = []
  assignments_in_modules = []
  quizzes_in_modules = []
  for module in modules:
    for item in module["items"]:
      if item["type"] == 'Discussion':
        print(item['content_id'])
        discussions_in_modules.append(item['content_id'])
      if item["type"] == 'Assignment':
        print(item['content_id'])
        assignments_in_modules.append(item['content_id'])

  url = f"{api_url}/courses/{course_id}/assignments"
  assignments = get_paged_data(url)


  assignments_to_delete = []
  discussions_to_delete =[]
  for assignment in assignments:
    #For now, we're not deleting quizzes
    #This stub is to keep them from being deleted and be a place if want to deal with them later
    if 'quiz_id' in assignment:
      continue

    if 'discussion_topic' in assignment:
      discussion = assignment["discussion_topic"]
      if discussion['id'] not in discussions_in_modules:
        discussions_to_delete.append(discussion)
      continue

    if assignment["id"] not in assignments_in_modules:
      assignments_to_delete.append(assignment)

  assignments_string = '\n'.join( list( map( lambda item: item["name"], assignments_to_delete)))
  if tk.messagebox.askyesno(message=f"Do you want to delete the following assignments?\n{assignments_string}"):
    for assignment in assignments_to_delete:
      result = requests.delete(f"{api_url}/courses/{course_id}/assignments/{assignment['id']}", headers=headers) 
      print(result)


  discussions_string = '\n'.join( list( map( lambda item: item["title"], discussions_to_delete)))
  if tk.messagebox.askyesno(message=f"Do you want to delete the following discussions?\n{discussions_string}"):
    for discussion in discussions_to_delete:
      result = requests.delete(f"{api_url}/courses/{course_id}/discussion_topics/{discussion['id']}", headers=headers) 
      print(result)

def remove_gallery_discussions(discussions, remove_introduction = True):
  print(discussions)
  gallery_discussions = []
  to_remove = []
  for discussion in discussions:
    #just throw away introductions
    if remove_introduction and "Introduction" in discussion["title"]:
      to_remove.append(discussion)

    print("removing gallery discussions")
    print(discussion['title'])
    print("Gallery in the title?", "allery" in discussion["title"])
    if re.search(r'allery', discussion['title']):
      gallery_discussions.append(discussion)
      to_remove.append(discussion)

  for discussion in to_remove:
    discussions.remove(discussion)
  return gallery_discussions

def duplicate_item(course_id, item, module=None):
  item_id =  item["url"].split('/')[-1] #grab the resource id off the end of the url
  type_ = item["type"]
  print(f"Duplicating assignment {item_id}")

  if type_ == "Assignment":
    url = f"{api_url}/courses/{course_id}/assignments/{item_id}/duplicate"
  elif type_ == "Discussion":
    url = f"{api_url}/courses/{course_id}/discussion_topics/{item_id}/duplicate"

  print(url)
  response = requests.post(url, headers=headers)
  if not response.ok:
    print(response)
    raise response.raise_for_status()
  item = response.json()

  item_name = ""
  if 'title' in item:
    item_name = item['title']
  elif 'name' in item:
    item_name = item['name']
  print(f"Adding {type_} {item_name} to module {module['name']}")
  url = f"{api_url}/courses/{course_id}/modules/{module['id']}/items"
  print(url)
  payload = {
    "module_item[title]" : item_name,
    "module_item[content_id]" : item["id"],
    "module_item[type]" : type_,
    "module_item[indent]" : 1,
    "module_item[position]" : 999
    }

  if type_ == "Assignment":
    payload["module_item[completion_requirement][type]"] = "must_submit"

  if type_ == "Discussion":
    payload["module_item[completion_requirement][type]"] = "min_score"
    payload["module_item[completion_requirement][min_score]"] = "1"

  print(payload)
  response = requests.post(url, headers=headers, data = payload)
  if not response.ok:
    print(response.json())
    raise response.raise_for_status()

  print(response.json())
  return item

def get_old_module_number(module):  
    title_words = module["name"].split(" ")
    if ( "week" in title_words[0].lower()):
      return title_words[1]
    return False

def get_old_module_title(module):  
    #if the module name is "Week X" return the name of the subheader
    title_words = module["name"].split(" ")
    if ( "week" in title_words[0].lower()):
      return module["items"][0]["title"]

    #if the module name is not "Week X" just return the full module name
    return module["name"]

def find_new_module_by_number(number, modules):
 return next( filter ( lambda module: f"Module {number}" in module["name"], modules) )

def update_weekly_overviews(course_id, old_course_id):
  url = f"{api_url}/courses/{old_course_id}/modules?include[]=items&include[]=content_details"
  response = requests.get(url, headers=headers)
  print(response.status_code)
  old_modules = response.json()

  url = f"{api_url}/courses/{course_id}/modules?include[]=items&include[]=content_details"
  response = requests.get(url, headers=headers)
  print(response.status_code)
  modules = response.json()

  for old_module in old_modules:
    print(old_module["name"])
    title_words = old_module["name"].split(" ")
    items = old_module["items"]
    if ("week" in title_words[0].lower()):


      i = int(title_words[1])
      module_name = old_module ['items'][0]["title"]

      module = next( filter ( lambda module: f"Module {i}" in module["name"], modules) )

      set_module_title(course_id, module["id"], f"Module {i} - {module_name}".title())
  
      old_overview_page_info = next(filter(lambda item: "overview" in item["title"].lower() and item["type"] == "Page", items))
      old_lo_page_info = next(filter(lambda item: "learning objectives" in item["title"].lower(), items))

      print(old_overview_page_info)
      old_overview_page = get_page_by_url (old_overview_page_info["url"])
      old_lo_page = get_page_by_url (old_lo_page_info["url"])
      overview_page = get_page_by_url (f"{api_url}/courses/{course_id}/pages/week-{i}-overview")

      old_overview_soup = BeautifulSoup(old_overview_page["body"], 'lxml')
      old_lo_soup = BeautifulSoup(old_lo_page["body"], 'lxml')

      #grab the list of learning objectives from the page
      learning_objectives = old_lo_soup.find('ul')
      if not learning_objectives:
        learning_objectives = old_lo_soup.find("ol")

      learning_objectives = learning_objectives.prettify()

      description_box = old_overview_soup.find("div", class_="column")
      description_elements = None
      if description_box:
        description_elements = list(description_box.children)
      else:
        description_elements = old_overview_soup.find_all('p')


      description = "\n".join( 
        map(lambda tag: str(tag), description_elements)
      )

      new_page_body = new_overview_page_html(overview_page["body"], module_name, description, learning_objectives)

      response = requests.put(f'{api_url}/courses/{course_id}/pages/{overview_page["url"]}', 
        headers = headers,
        data = {
          "wiki_page[body]" : new_page_body
        }
      )  
     
def set_module_title(course_id, module_id, title ):
  url = f"{api_url}/courses/{course_id}/modules/{module_id}"
  print(url)
  response = requests.put(url, 
    headers = headers,
    data = {
      "module[name]" : title
    }
  )  
  print(response.text)

def new_overview_page_html(overview_page_body, title, description, learning_objectives):
  body = overview_page_body 
  soup = BeautifulSoup(body, "lxml")
  contents = soup.find_all("div", class_ = "content")
  contents[0].string = "[Insert text]"
  contents[1].string = "[insert weekly objectives, bulleted list]"

  body = soup.prettify()

  body = re.sub('\[title of week\]', f"{title}", body)
  body = re.sub('\[Insert.*text\]', f"{description}", body)
  body = re.sub('\[insert weekly objectives, bulleted list\]', f"{learning_objectives}", body)
  return body

def get_page_by_url(url):
  response = requests.get(url, headers=headers)
  page = response.json()
  return page

def get_file_url_by_name(course_id, file_search):
  url = f"{api_url}/courses/{course_id}/files"
  response = requests.get(url, headers=headers, params={"search_term" : file_search})
  files = response.json()
  if len(files) > 0:
    return files[0]["url"]
  return false

def update_syllabus_and_overview(course_id, old_course_id):
  old_page = get_syllabus(old_course_id)
  new_page = get_syllabus(course_id)



  syllabus_banner_url = get_file_url_by_name(course_id, "Module 1 banner (7)")


  is_course_grad = not old_page.find(string="Poor, but Passing")

  title = find_syllabus_title(old_page)
  description_paras = get_section(old_page, "Description:")
  print('DESCRIPTION')
  print(description_paras)
  learning_objectives_paras = get_section(old_page, "Outcomes:")
  textbook_paras = get_section(old_page, "Textbook:")
  week_1_preview = get_week_1_preview(course_id, old_course_id)

  term = "DE8W01.08.24" if is_course_grad else "DE/HL-24-Jan"
  dates = "January 8 - March 3" if is_course_grad  else "January 15 - February 18" 

  try:
    with open("syllabus_template.html", 'r') as f:
      template = f.read()
      text = template.format(
        banner_url = syllabus_banner_url,
        course_id = course_id,
        term_code = term,
        term_dates = dates,
        course_outcomes = "\n".join(map(lambda p: p.prettify(), learning_objectives_paras)),
        course_description = "\n".join(map(lambda p: p.prettify(), description_paras)),
        course_title = title,
        week_1_learning_materials = week_1_preview,
        textbook = "\n".join(map(lambda p: p.prettify(), textbook_paras)),
      )
  except Exception as e:
    print(type(e))
    print(e)
    tk.messagebox.showerror(message=f'''
      syllabus_template.html problem. It may be missing or out of date. Please download the latests from drive.
      {type(e)}
      {e.args}      
      {e}
      ''')
    exit()

  #update the new syllabus
  submit_soup = BeautifulSoup(text, "lxml")


  if is_course_grad:
    for el in list ( submit_soup.find_all("p", class_ = "undergrad") ):
      el.decompose()
    for el in list ( submit_soup.find_all("div", class_ = "undergrad") ):
      el.decompose()
  else:
    for el in list ( submit_soup.find_all("p", class_ = "grad") ):
      el.decompose()
    for el in list ( submit_soup.find_all("div", class_ = "grad") ):
      el.decompose()

  response = requests.put(f'{api_url}/courses/{course_id}', 
    headers = headers,
    data = {
      "course[syllabus_body]" : submit_soup.prettify()
    }
  )


  print(response.status_code)


  url = f"{api_url}/courses/{course_id}/modules?include[]=items&include[]=content_details"
  response = requests.get(url, headers=headers)
  print(response.status_code)
  modules = response.json()

  overview_module = next(filter(lambda module: module["position"] == 1, modules))
  page_id  = overview_module['items'][0]['page_url']
  url = f"{api_url}/courses/{course_id}/pages/{page_id}"

  response = requests.get(url, headers=headers)
  print(response.status_code)
  overview_page = response.json()

  overview_html = overview_page["body"]
  og_ov_soup = BeautifulSoup(overview_html, "lxml").body
  overview_banner_img = og_ov_soup.find("div", class_="cbt-banner-image").find('img')
  overview_banner_url = overview_banner_img["src"]

  #get assignment groups
  url = f"{api_url}/courses/{old_course_id}/assignment_groups"
  response = requests.get(url, headers=headers)
  groups = response.json()
  assignment_categories = groups

  #assignment weight text
  table_body = ""
  for assignment in assignment_categories:
    assignment["description"] = ""
    if "discussion" in assignment["name"].lower():
      assignment["description"] = 'Initial posts due by 3AM ET Thursday night, responses due by 3AM ET Monday night - unless otherwise noted.'

    if "assignment" in assignment["name"].lower():
      assignment["description"] = "Due by the end of the week in which they're assigned."

    table_body = table_body + f'''
    <tr style="height: 167px;">
      <td>{assignment["name"].title()}</td>
      <td>{assignment["description"]}</td>
      <td>{int(assignment["group_weight"])}%</td>
    </tr>
    '''

  try:
    with open("overview_template.html", 'r') as f:
      template = f.read()
      text = template.format(
        banner_url = overview_banner_url,
        course_id = course_id,
        course_outcomes = "\n".join(map(lambda p: p.prettify(), learning_objectives_paras)),
        course_description = "\n".join(map(lambda p: p.prettify(), description_paras)),
        table_body = table_body,
        textbook = "\n".join(map(lambda p: p.prettify(), textbook_paras)),
      )
  except Exception as e:
    print(type(e))
    print(e)
    tk.messagebox.showerror(message=f"overview_template.html problem. It may be missing or out of date. Please download the latests from drive.\n{e}\n{e.args}")
    exit()




  submit_soup = BeautifulSoup(text, "lxml")

  response = requests.put(f'{api_url}/courses/{course_id}/pages/course-overview', 
    headers = headers,
    data = {
      "wiki_page[body]" : submit_soup.prettify()
    }
  )  


def get_syllabus(course_id):
  url = f"{api_url}/courses/{course_id}?include[]=syllabus_body"
  response = requests.get(url, headers=headers)
  content = response.json()
  return BeautifulSoup(content["syllabus_body"], "lxml")

def find_syllabus_title(soup):
  header = soup.find("strong", string=re.compile("course number and title", re.IGNORECASE))
  title_p = header.find_parent("p")
  header.decompose()
  return title_p.text

def get_section(soup, header_string):
  header = soup.find("h4", text=re.compile(header_string, re.IGNORECASE))
 

  if not header:
    header = soup.find("strong", text=re.compile(header_string, re.IGNORECASE))
    print (header)
    if not header:
      return BeautifulSoup(f"<p>---Section {header_string} not found.---</p>", "lxml").find_all("p")
    parent = header.parent
    header = parent

  paragraphs = []

  el =  header.find_next_sibling()
  print(el.name)
  while el and el.name != "h4" and not len(list(el.find_all('strong', string=re.compile(r':')))) > 0 and not len(el.text) < 5:
    paragraphs.append(el)
    el = el.find_next_sibling()

  print(paragraphs)
  return paragraphs


def replace_content(soup, header_string, list_of_new_contents):
  container = soup.find("h2", string=header_string).parent

  #remove existing paras
  for el in container.find_all("p"):
    el.decompose()
  for el in list_of_new_contents:
    container.append(el)

  print(container)

#https://codereview.stackexchange.com/questions/272811/converting-a-youtube-embed-link-to-a-regular-link-in-python
def convert_to_watch_url(embed_url: str) -> str:
    """Convert a YouTube embed URL into a watch URL."""

    scheme, netloc, path, params, query, fragment = urlparse(embed_url)
    video_id, path = Path(path).stem, '/watch'
    return urlunparse((scheme, netloc, path, params, f'v={video_id}', fragment))


def get_week_1_preview(course_id, old_course_id):

    old_lm_url = f"{api_url}/courses/{old_course_id}/pages/week_1_learning_materials"
    lm_response = requests.get(old_lm_url, headers=headers)

    print(lm_response)

    lm_page = lm_response.json()
    lm_soup = BeautifulSoup(lm_page["body"], "lxml")

    h4 = lm_soup.find("h4")
    learning_materials = None
    if h4:
      learning_materials = list(h4.next_siblings)
    else:
      learning_materials = list(get_section(lm_soup, "Please read (and watch )?the following materials:"))

    iframe = lm_soup.find("iframe")
    youtube_iframe_source = iframe["src"]
    links = lm_soup.find_all("a")
    transcripts = []
    slides = []
    for link in links:
      if 'ranscript' in link.text:
        transcripts.append(link)
      if 'lides' in link.text:
        slides.append(link)



    temp_soup = BeautifulSoup(f"<ul><li><a href={convert_to_watch_url(youtube_iframe_source)}>Week 1 Lecture</a><ul class='transcripts'></ul></li></ul>", "lxml")
    list_ = temp_soup.find("ul", class_="transcripts")
    print(transcripts)
    for transcript in transcripts:
      li = temp_soup.new_tag("li")
      a = temp_soup.new_tag("a")
      a.string = "transcript"
      a["href"] = transcript["href"]
      li.append(a)
      list_.append(li)
    for slide in slides:
      li = temp_soup.new_tag("li")
      a = temp_soup.new_tag("a")
      a.string = "slides"
      a["href"] = slide["href"]
      li.append(a)
      list_.append(li)

    for item in learning_materials:
      temp_soup.body.append(item)

    update_links(temp_soup, {
      "course_id" : course_id,
      "old_course_id" : old_course_id,
      "assignments_lut" : get_assignments_lookup_table(get_modules(course_id), get_modules(old_course_id), course_id, old_course_id)
      })


    return temp_soup.body


def get_latest_lm_backup(course_id, week_num):
  url = f"{api_url}/courses/{course_id}/pages/"
  print(url)
  response = requests.get(url, headers=headers, data={
    "sort" : "created_at",
    "search_term" : f"Week {week_num} Learning Materials"
    })
  if not response.ok:
    raise Exception(response.json())
  print(response)

  if len(response.json()) < 2:
    return False

  old_lm_url = response.json()[-1]["url"]
  return old_lm_url

def update_learning_materials(course_id, old_course_id, files_lut, assignments_lut ):
  print("Updating Learning Materials")
  for i in range(1,9):



    old_url = f"{api_url}/courses/{old_course_id}/pages/week_{i}_learning_materials"
    new_url = f"{api_url}/courses/{course_id}/pages/week_{i}_learning_materials"
    #old_url = get_latest_lm_backup(course_id, i)
    print(f"copying from {old_url} to {new_url}")

    old_page_response = requests.get(old_url, headers=headers)
    if not old_page_response.ok:
      continue
    old_page = old_page_response.json()

    new_page_response = requests.get(new_url, headers=headers)
    if not new_page_response.ok:
      continue
    new_page = new_page_response.json()

    old_soup = BeautifulSoup(old_page["body"])
    new_soup = BeautifulSoup (new_page["body"])
    
    #handle youtube links
    old_iframes = list( old_soup.find_all("iframe") )
    new_iframes = new_soup.find_all("iframe")

    youtube_iframe_source = old_iframes[0]["src"]
    new_iframes[0]["src"] = youtube_iframe_source


    old_header = old_soup.find("h4")
    learning_materials = None
    if old_header:
      learning_materials = list(old_header.next_siblings)
      
    else:
      learning_materials = get_section(old_soup, "Please read (and watch )?the following materials:")
    
    print(learning_materials)
    #handle transcripts
    transcripts_and_slides = old_soup.find_all("div", {'class':"column"})[1].find_all("a")
    transcripts = list( filter(lambda el: "transcript" in el.text.lower(), transcripts_and_slides))
    slides = list( filter(lambda el: "slides" in el.text.lower(), transcripts_and_slides))


    canon_transcripts = []
    canon_slides = []
    for item in transcripts:
      canon_transcripts.append(item)
    for item in slides:
      canon_slides.append(item)

    buttons = new_soup.find_all("p", { "class" : "cbt-button"})
    slides_buttons = []
    transcript_buttons = []

    for button in buttons:
      if button.find("a", string=re.compile("Slides",re.IGNORECASE)):
        slides_buttons.append( button.find("a", string=re.compile("Slides",re.IGNORECASE)) )
      if button.find("a", text=re.compile("Transcript", re.IGNORECASE)):
        transcript_buttons.append( button.find("a", string=re.compile("Transcript", re.IGNORECASE)) )

    slides_count = 0
    transcripts_count = 0
    old_transcript_button = None

    if True: #this is here to clear out a bunch of buttons
      button_count = len(transcript_buttons)

      if button_count > 1:
        for i in range(1, button_count):
          button = transcript_buttons[i]
          button.parent.extract()

      button_count = len(slides_buttons)
      if len(slides_buttons) > 1:
        button = slides_buttons[i]
        for i in range(1, button_count):
          button.parent.extract()



    #clean up secondary media boxes
    secondary_media_boxes = get_secondary_media_boxes(new_soup)


    #if there are more than one old iframe, we're gonna make secondary media boxen to match, if we have a secondary media box to go on
    total_needed_boxes = len(old_iframes) - 1
    if len( old_iframes ) > 1 and len ( secondary_media_boxes ) > 0:
        boxes_to_add = total_needed_boxes - len (secondary_media_boxes)
        last_box = secondary_media_boxes[-1]
        if boxes_to_add > 0:
          new_box = copy.copy(last_box)
          last_box.insert_after(new_box)
          last_box = new_box

    secondary_media_boxes = get_secondary_media_boxes(new_soup)
    for i in range(0, len(secondary_media_boxes)):
      box = secondary_media_boxes[i]
      if i <= total_needed_boxes - 1:
        box.find("iframe")['src'] = old_iframes[i + 1]["src"]
      else:
        box.decompose()

    #save off originals so we can append them to acordion later



    if len(transcripts) > 0:
      old_button = transcript_buttons[0]
      old_button["body"] = f"Transcript"
      old_button["href"] = transcripts[0]["href"]
      transcripts.remove(transcripts[0])

    if len(slides) > 0:
      old_button = slides_buttons[0]
      old_button["body"] = f"Slides"
      old_button["href"] = slides[0]["href"]
      slides.remove(slides[0]) 
    else:
      for button in slides_buttons:
        button.decompose()

    i = 0

    if secondary_media_boxes:
      for box in secondary_media_boxes:
        if i < len(transcripts):
          transcript = transcripts[i]
          link = box.find('a', id=f"transcript_link_{i}")
          print("---")
          print(link)
          print("---")
          if not link:
            link = new_soup.new_tag('a', string="transcript", id=f"transcript_link_{i}")
            p = box.find('p')
            p.insert(0, link)
            print(box)

          link["href"] = transcript["href"]
          link.string = "transcript"

        if i < len(slides):
          slide = slides[i]
          link = box.find('a', id=f"slides_link_{i}")
          if not link:
            link = new_soup.new_tag('a', string="slides", class_="slides_link", id=f"slides_link_{i}")
            link["class"] = "slides_link"
            p = box.find('p')
            p.append(link)
          link["href"] = slides["href"]


      i = i + 1




    #handle learning materials

    #make a new accordion and just all the learning materials into it IF this accordion is a template
    accordion_list = list(new_soup.find_all("div", class_='auto-add'))
    accordion = None
    if accordion_list and len(accordion_list) > 0:
      accordion = accordion_list[-1]
    if not accordion:
      accordion = new_soup.find("div", class_="cbt-accordion-container")

      if accordion.find(text=re.compile("Title for first category of LMs", re.IGNORECASE)):
        print("adding Learning Materials")
        new_content = copy.copy(accordion)
        accordion.parent.append(new_content)
        new_content['class'].append('auto-add')
        content = new_content.find("div", class_="cbt-answer")
        for transcript in canon_transcripts:
          content.append(transcript)
        for slide in canon_slides:
          content.append(slide)
        for el in learning_materials:
          content.append(el)
    else:
      content = accordion.find("div", class_="cbt-answer")
      content.clear()
      for transcript in canon_transcripts:
        content.append(transcript)
      for slide in canon_slides:
        content.append(slide)
      for el in learning_materials:
        content.append(el)



    #update links
    update_links(new_soup, {
      "course_id" : course_id,
      "old_course_id" : old_course_id,
      "files_lut" : files_lut,
      "assignments_lut" : assignments_lut,
      })

    #save changes
    response = requests.put(f'{api_url}/courses/{course_id}/pages/{new_page["page_id"]}', 
      headers = headers,
      data = {
        "wiki_page[body]" : new_soup.prettify()
      }
    )
    print(new_page["title"],response.status_code)

def get_secondary_media_boxes(soup):
  secondary_media_boxes = []
  h3s = soup.find_all('h3')
  for h3 in h3s:
    if "secondary media element" in h3.text:
      secondary_media_boxes.append(h3.parent)
  return secondary_media_boxes

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