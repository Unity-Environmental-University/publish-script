import glob
import traceback
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
import argparse

ADD_LEARNING_MATERIALS = False
UPDATE_SYLLABUS = True
CONSTANTS_FILE = "constants.json"
GRAD_TERM_NAME = "DE8W01.08.24"
UG_TERM_NAME = "HL-24-Jan"
GRADE_TERM_DATES = "January 8 - March 3"
UG_TERM_DATES = "January 15 - February 18" 
HOMETILE_WIDTH = 512
GRAD_SCHEME_NAME = "DE Graduate Programs"


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

  #account_id = ACCOUNT_ID

except Exception as e:
  print(e)
  tk.messagebox.showerror(message=f"It looks like your constants file is missing some values. Ask hallie for a current copy of the constants.json file.\n{e}")


# Authorize the request.
headers = {
  "Authorization": f"Bearer {api_token}",
  "User-Agent" : 'UnityThemeMigratorBot/0.0 (http://unity.edu; hlarsson@unity.edu)'
}
img_headers = {
  "User-Agent" : 'UnityThemeMigratorBot/0.0 (http://unity.edu; hlarsson@unity.edu)'
}


url = f'{api_url}/accounts'
accounts = requests.get(url, headers=headers).json()
account_ids = dict()
for account in accounts:
  account_ids[account['name']] = account['id']

ACCOUNT_ID = account_ids['Distance Education']
ROOT_ACCOUNT_ID = account_ids['Unity College']


print(ACCOUNT_ID, ROOT_ACCOUNT_ID)

account_id = ACCOUNT_ID
def main():
  course_id = 0
  source_course_id = 0

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

  if not source_course_id or source_course_id == 0:
    code = course["course_code"].split("_")[1][0:7]
    print("Code", code)
    #look for dep or deprecated first

    response = requests.get(f"{api_url}/accounts/{account_id}/courses", headers=headers, params = {"search_term" : f"DEPRECATED_{code}"} )
    courses = response.json()
    print(courses)
    if len(courses) == 0:
      response = requests.get(f"{api_url}/accounts/{account_id}/courses", headers=headers, params = {"search_term" : f"DEP_{code}"} )
      courses = response.json()
      print(courses)
      #if that's not there, look for DEV assuming DEP has not been made
    if len(courses) == 0:
      response = requests.get(f"{api_url}/accounts/{account_id}/courses", headers=headers, params = {"search_term" : f"DEV_{code}"} )
      courses = response.json()
      print(courses)


    for course in courses:
      print(course["course_code"])
    if len(courses) > 1:
      courses.sort(key=lambda course: course['id'], reverse=True)

    if len(courses) > 0:
      source_course_id = courses[0]["id"]
      print("Old course found", source_course_id, courses[0]["course_code"])


  updates = [
    { 
      'name': 'syllabus and course overview',
      'argument': 'syllabus',
      'message': 'Do you want to update the syllabus and course overview?',
      'error': 'There was a problem updating the syllabus and overviews\n{e}',
      'func': update_syllabus_and_overview,
    },
    { 
      'name': 'overviews',
      'message': 'Do you want to try to update the weekly overviews?',
      'error': 'There was a problem updating weekly overviews\n{e}',
      'func': update_weekly_overviews,
    },
    { 
      'name' : 'assignments',
      'message' : 'Do you want to try to update assignments?',
      'error' : 'There was a problem updating assignments\n{e}',
      'func' : align_assignments,
    },
    { 
      'name' : 'learning_materials',
      'argument' : 'lm',
      'message' : 'Do you want to try to update learning materials?',
      'error' : 'There was a problem updating learning materials\n{e}',
      'func' : update_learning_materials_cl,
    },
    { 
      'name' : 'rubrics',
      'message' : 'Do you want to try to update rubrics?',
      'error' : 'There was a problem updating rubrics\n{e}',
      'func' : align_rubrics,
    },
    { 
      'name' : 'delete',
      'message' : 'Do you want to try to delete assignments not in discussions and modules?\nYou will see a list of items to confirm.',
      'error' : 'There was a problem deleting these assignments\n{e}',
      'func' : remove_assignments_and_discussions_not_in_modules,
    },
    { 
      'name' : 'hometiles',
      'message' : 'Do you want to automatically make hometiles based on overview banners?',
      'error' : 'There was a problem creating hometiles\n{e}',
      'func' : set_hometiles,
    },

  ]

  #Check if the arguments are on the command line and run those options that are
  if len(sys.argv) > 2:
    for update in updates:
      if update['name'] in sys.argv or 'argument' in update and update['argument'] in sys.argv:
        update['func'](course_id, source_course_id)


  #if we don't have any arguments past the id, go into interactive mode
  else:
    opening_dialog(course_id, source_course_id, updates)


def opening_dialog(course_id, source_course_id, updates):
  root = tk.Tk()
  checkboxes = []

  # terms = requests.get(f'{api_url}/accounts/{ROOT_ACCOUNT_ID}/terms', headers=headers).json()['enrollment_terms']
  # print(terms)
  # terms.sort(key=lambda term: term['id'], reverse=True)
  # term_name_var = tk.StringVar()
  # term_name_var.set(terms[0]['name'])
  # term_name_input = tk.Entry(root, text="Term Code", textvariable= term_name_var)
  # #term_name_input.pack()


  for update in updates:
    boolVar = tk.BooleanVar()
    button =  tk.Checkbutton(root, text=update['message'], onvalue = True, offvalue=False, variable= boolVar)
    checkboxes.append(button)
    update['run'] = boolVar
    button.pack()

  button = tk.Button(master=root, text="Run", command=lambda: run_opening_dialog(root, course_id, source_course_id, updates))
  button.pack()
  #button = tk.Button(master=root, text="ADVANCED OPTIONS", command=lambda: advanced_options_ui(root, course_id, source_course_id))
  #button.pack()

  root.mainloop()

def run_opening_dialog(root, course_id, source_course_id, updates):
  label = tk.Label(root, text="Select which steps to perform")
  label.pack()
  for update in updates:
    try:
      if update['run'].get():
        label.config(text=f"Running {update['name']}")
        root.update()
        print(update)
        update['func'](course_id, source_course_id)
    except Exception as e:
      tk.messagebox.showerror(message=update['error'].format( e=str(e)) + "\n" + traceback.format_exc())
      print(traceback.format_exc())


  root.destroy()
  tk.messagebox.showinfo(message="Finished!")



def advanced_options_ui(root, course_id, source_course_id):
  advanced_options = [
    {
      'name' : "Revert Assignment Changes",
      'func' : revert_assignments,
      'show' : False,
    }
  ]
  win = tk.TopLevel(root)


  for option in advanced_options:
    button = tk.Button(master=win, text=option['name'], command=lambda: execute_option(win, course_id, source_course_id, option))
    button.pack()

  win.mainloop()

def execute_option(win, course_id, source_course_id, option):
  option['func'](course_id, source_course_id)
  win.destroy()

def revert_assignments(course_id, source_course_id):
  assignments = get_paged_data(f"{api_url}/courses/{course_id}/assignments")
  discussions = get_paged_data(f"{api_url}/courses/{course_id}/discussion_topics")
  
  win = tk.Tk()


  options = []

  for assignment in assignments:
    assignment_id = assignment['id']
    if get_backup(course_id, assignment_id, "assignments"):
      bool_var = tk.BooleanVar()
      cb = tk.Checkbutton(master=win, text=assignment['name'], onvalue = True, offvalue=False)
      cb.var = bool_var
      cb.pack(anchor="w")
      options.append( { 
        'control' : cb,
        'checked' : bool_var,
        'func' : revert_assignment,
        'item_id' : assignment_id

      })

  for discussion in discussions:
    discussion_id = discussion['id']
    if get_backup(course_id, discussion_id, "discussions"):
      bool_var = tk.BooleanVar()
      cb = tk.Checkbutton(master=win, text=discussion['title'], onvalue = True, offvalue=False)
      cb.pack(anchor="w")
      cb.var = bool_var
      options.append( { 
        'control' : cb,
        'checked' : bool_var,
        'func' : revert_discussion,
        'item_id' : discussion_id
      })

  button = tk.Button(master=win, text="Revert", command=lambda: click_revert_assignments(course_id, win, options))
  button.pack()


def click_revert_assignments(course_id, win, options):
  print("Reverting")
  for option in options:
    print(option, option['control'].var.get())
    #if the boolean of the checkbox is checked, run the callback
    if option['control'].var.get():
      print(option['func'])
      option['func'](course_id, option['item_id'])

  win.destroy()


def revert_assignment(course_id, assignment_id):
  print('reverting', assignment_id)
  backup = get_backup(course_id, assignment_id, "assignments")
  if not backup:
    print("no backup found for " + str(assignment_id))
    return False
  url = f"{api_url}/courses/{course_id}/assignments/{assignment_id}"
  response = requests.put(url, headers=headers, data={
    'assignment[name]' : backup['name'],
    'assignment[description]' : backup['description']

    })
  print(response)

def revert_discussion(course_id, discussion_id):
  backup = get_backup(course_id, discussion_id, "discussions")
  if not backup:
    print("no backup found for " + str(discussion_id))
    return False
  url = f"{api_url}/courses/{course_id}/discussion_topics/{discussion_id}"
  response = requests.put(url, headers=headers, data={
    'title' : backup['title'],
    'message' : backup['message']
    })
  print(response)

def get_backup(course_id, item_id, backups_folder):
  base_folder = "course_data"
  folder_path = os.path.join(os.getcwd(), base_folder, str(course_id), backups_folder, str(item_id))
  ensure_directory_exists(folder_path)
  list_of_files = glob.glob(f'{folder_path}/*.json')
  if len(list_of_files) == 0:
    return False
  filename = f"{item_id}_{len(list_of_files) - 1}.json"

  with open(os.path.join(folder_path, filename) , 'r') as f:
    print(f)
    return json.load(f)

  

def confirm_dialog(message):
  root = tk.Tk()
  root.withdraw()
  out = tk.messagebox.askyesno(message=message)
  return out

def update_assignment_categories(course_id, source_course_id):
  url = f"{api_url}/courses/{source_course_id}/assignment_groups"
  response = requests.get(url, headers=headers)
  source_groups = response.json()
  
  url = f"{api_url}/courses/{course_id}/assignment_groups"
  response = requests.get(url, headers=headers)
  destination_groups = response.json()

  for group in source_groups:
    dest_group = next( filter( lambda x: x['name'] == group['name'], destination_groups), None)
    if dest_group:
      url = f"{api_url}/courses/{course_id}/assignment_groups/{dest_group['id']}"
      response = requests.put(url, headers=headers, data={
        'group_weight' : group['group_weight'],
        'position' : group['position'],
        })
      print (response)
      assert response.ok, "There was a problem updating assignment groups"
    else:
      url = f"{api_url}/courses/{course_id}/assignment_groups/"
      response = requests.post(url, headers=headers, data={
        'name' : group['name'],
        'group_weight' : group['group_weight'],
        'position' : group['position'],
        })
      print (response)
      assert response.ok, "There was a problem updating assignment groups"

def set_hometiles(course_id, source_course_id=None):
    # Retrieve the home page content
    home_page_url = f"{api_url}/courses/{course_id}/pages/home"
    response = requests.get(home_page_url, headers=headers)
    page = response.json()
    soup = BeautifulSoup(page["body"], 'lxml')

    # Set up directories for storing images
    image_path = setup_image_directories(course_id)

    # Process and upload the main hometile
    process_and_upload_main_hometile(course_id, image_path, soup)

    # Process and upload hometiles for weekly overviews
    process_and_upload_overview_tiles(course_id, source_course_id, image_path)


def setup_image_directories(course_id, base_folder="course_data"):
    # Set up directories for storing images
    image_path = os.path.join(os.getcwd(), base_folder, str(course_id))
    ensure_directory_exists(image_path)
    return image_path

def process_and_upload_main_hometile(course_id, image_path, soup):
    # Process and upload the main hometile
    banner = soup.find("div", class_="cbt-banner-image").find('img')
    img_data, ext = retrieve_image(banner['src'], course_id, 1)
    home_tile_path = save_hometile(img_data, image_path, f"hometile1.{ext}")
    upload_hometile(course_id, home_tile_path)

def process_and_upload_overview_tiles(course_id, image_source_course_id, image_path):
    # Process and upload hometiles
    modules = get_modules(course_id)
    for i, module in enumerate(modules, start=1):
      overview_url = f"{api_url}/courses/{course_id}/pages/week_{i}_overview"
      response = requests.get(overview_url, headers=headers)
      
      if response.ok:
        page = response.json()
        soup = BeautifulSoup(page["body"], 'lxml')
        
        banner = soup.find("div", class_="cbt-banner-image").find('img')
        img_data, ext = retrieve_image(banner['src'], course_id, i + 1)
        
        home_tile_path = save_hometile(img_data, image_path, f"hometile{i + 1}.{ext}")
        upload_hometile(course_id, home_tile_path)

def retrieve_image(src, course_id, tile_number):
    # Retrieve and save image data
    response = requests.get(src, headers=img_headers)
    img_data = response.content
    ext = "png" if 'png' in response.headers["Content-Type"] else 'jpg'
    return img_data, ext


def ensure_directory_exists(directory_path):
    # Ensure the directory exists; create if not
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


def upload_hometile(course_id, local_path):
  #get the correcy folder id
  url = f"{api_url}/courses/{course_id}/folders/by_path/Images/hometile"
  response = requests.get(url, headers=headers)
  folders = response.json()
  hometile_folder = folders[-1]

  #upload the file
  file_url = f"{api_url}/courses/{course_id}/files"
  print(f"uploading {local_path} to {file_url}")
  data = {
    "name" : os.path.basename(local_path),
    "no_redirect" : True,
    "parent_folder_id" : hometile_folder["id"],
    "on_duplicate" : "overwrite"
  }

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

#saves hometile to disc
def save_hometile(img_data, data_folder, filename):
  filepath = os.path.join(data_folder, filename)

  with open(filepath, 'wb') as file:
    file.write(img_data)

  with Image.open(filepath) as img:
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
  url = f"{api_url}/courses/{course_id}/modules?include[]=items&include[]=content_details&per_page=100"
  return get_paged_data(url)
  
def create_missing_assignments(modules, source_modules, course_id, source_course_id):
  print("Creating missing assignments")
  modules = get_modules(course_id)
  source_modules = get_modules(source_course_id)

  handled = []
  count = 0
  print(source_modules)
  for source_module in source_modules:
    items = source_module["items"]
    #skip non-week modules
    number = get_source_module_number(source_module)
    name = get_source_module_title(source_module)
    if not number:
      continue

    module = find_new_module_by_number(number, modules)

    #save off the gallery discussion
    if number == "1":
      gallery_search = filter( lambda item: "Gallery Discussion" in item["title"], module["items"])
      gallery_discussion_template = next( filter( lambda item: "Gallery Discussion" in item["title"], module["items"]), None)

    count = count + create_missing_assignments_in_module(module, source_module, course_id, source_course_id, gallery_discussion_template)
    handled.append(module)

  #remove named modules that were not handled
  to_remove = list( filter( lambda module: (not module in handled) and "Module" in module["name"], modules))
  module_name_list = "\n".join(list( map(lambda module: module["name"], to_remove)))
  if len(to_remove) and tk.messagebox.askyesno(message=f"Do you want to remove the following modules and their contents?\n{module_name_list}"):
    for module in to_remove:
      remove_module(course_id, module, True)
  return { "added" : count, "removed" : count }



def remove_module(course_id, module, delete_contents):
  if delete_contents:
    for item in module["items"]:
      url = item["url"]
      print(f"Deleting {url}")
      result = requests.delete(url, headers=headers)

  url = f"{api_url}/courses/{course_id}/modules/{module['id']}"
  result = requests.delete(url, headers=headers)


def create_missing_assignments_in_module(module, source_module, course_id, source_course_id, gallery_discussion_template):
  count = 0
  count = count + add_quizzes(module, source_module, course_id, source_course_id)
  count = count + add_assignments(module, source_module, course_id, source_course_id)
  count = count + add_discussions(module, source_module, course_id, source_course_id, gallery_discussion_template)
  return count

def add_quizzes(module, source_module, course_id, source_course_id):
  source_quizzes = list ( filter( lambda item: item["type"] == "Quiz", source_module["items"]) )
  quizzes = list( filter( lambda item: item["type"] == "Quiz", module["items"]) )

  count = 0
  difference = len(source_quizzes) - len(quizzes)

  if difference > 0:
  #we're looking for imported quizzes now

    url = f"{api_url}/courses/{course_id}/quizzes"
    all_quizzes_in_course = get_paged_data(url)
    for source_quiz in source_quizzes:
      #if the quiz is there, we're good
      if next(filter(lambda item: item["title"] == source_quiz["title"], quizzes), None):
        continue
      else:
        count = count + 1
        print("Adding Quiz To Module")
        print( list(map( lambda quiz: f"{quiz['title']} // {source_quiz['title']}  // {quiz['title'] in source_quiz['title']}", all_quizzes_in_course)))
        new_quiz = next( filter(lambda item: item["title"].lower() in source_quiz["title"].lower(), all_quizzes_in_course), None)
        assert new_quiz, f"Quiz not found:{source_quiz['title']}"
        url = f"{api_url}/courses/{course_id}/modules/{module['id']}/items"
        result = requests.post(url, headers=headers, data={
          "module_item[type]" : "Quiz",
          "module_item[content_id]" : new_quiz["id"],
          "module_item[completion_requirement][type]" : "must_submit" ,
          "module_item[indent]" : 1,
          "module_item[position]" : 999
          })
  return count

def add_assignments(module, source_module, course_id, source_course_id):
  source_assignments = list ( filter( lambda item: item["type"] == "Assignment", source_module["items"]) )
  assignments = list( filter( lambda item: item["type"] == "Assignment", module["items"]) )
  difference = len(source_assignments)  - len(assignments)
  if difference > 0:
    added_items = True

    for _ in range(0, difference):
      duplicate_item(course_id, assignments[0], module)
  return difference

def add_discussions(module, source_module, course_id, source_course_id, gallery_discussion_template):
  #get discussions and pull out gallery discussions to handle differently
  source_discussions = list ( filter( lambda item: item["type"] == "Discussion", source_module["items"]) )
  source_gallery_discussions = remove_gallery_discussions(source_discussions)

  discussions = list( filter( lambda item: item["type"] == "Discussion", module["items"]) )
  gallery_discussions = remove_gallery_discussions(discussions)

  count = 0
  #if we don't have a gallery discussion template, just duplicate the first discussion if there is one
  if not gallery_discussion_template and len(discussions) > 0:
    gallery_discussion_template = discussions[0]

  #add discussions if there is disparity
  difference = len(source_discussions)  - len(discussions)
  if difference > 0:
    added_items = True

    #duplicate the first discussion as many times as it takes to get parity between discussions
    for _ in range(0, difference):
      duplicate_item(course_id, discussions[0], module)

  count = count + difference

  difference = len(source_gallery_discussions)  - len(gallery_discussions)
  if difference > 0:
    added_items = True

    #duplicate the gallery discussion template as many times as it takes to get parity between gallery discussions
    for _ in range(0, difference):
      duplicate_item(course_id, gallery_discussion_template, module)

  count = count + difference

  return count


#makes a lookup table of all files in the new course vs all file ids in the old course, and then caches that result for the rest of execution
files_lut_cache = None
def get_files_lookup_table(course_id, source_course_id, force=False):
  global files_lut_cache
  base_folder = "course_data"
  folder_path = os.path.join(os.getcwd(), base_folder, str(course_id))
  ensure_directory_exists(folder_path)
  data_path = os.path.join(folder_path, "files.json")

  #If we're not forcing it, try to return cached version (either in ram or on disk)
  if not force:
    if files_lut_cache:
      return files_lut_cache

    if not files_lut_cache:
      if os.path.isfile(data_path):
        with open(data_path, 'r') as f:
          files_lut_cache = json.load(f)
          return files_lut_cache

  files = get_paged_data(f"{api_url}/courses/{course_id}/files?per_page=100")
  source_files = get_paged_data(f"{api_url}/courses/{source_course_id}/files?per_page=100")


  files_lut = dict()
  for source_file in source_files:
    #match files by name and size
    print(source_file)
    file = next( filter( lambda a: source_file["filename"] == a["filename"], files), None)
    assert file, f"File {source_file['filename']} not found in new course. You may need to import files."
    files_lut[str(source_file["id"])] = file

  files_lut_cache = files_lut
  with open(data_path, 'w') as f:
    json.dump(files_lut, f, indent=2)

  return files_lut 

def get_course(course_id):
  url = f'{api_url}/courses/{course_id}'
  response = requests.get(url, headers=headers)
  log(response)
  return response.json()


#makes a lookup table of all assignments (and discussions) in the new course via ids of assignments (and discussions) in the old course, and then caches that result for the rest of execution
assignments_lut_cache = None
def get_assignments_lookup_table(course_id, source_course_id, force=False):
  global assignments_lut_cache
  base_folder = "course_data"
  folder_path = os.path.join(os.getcwd(), base_folder, str(course_id))
  ensure_directory_exists(folder_path)
  data_path = os.path.join(folder_path, "assignments.json")

  #If we're not forcing it, try to return cached version (either in ram or on disk)
  if not force:
    if assignments_lut_cache:
      return assignments_lut_cache

    if not assignments_lut_cache:
      if os.path.isfile(data_path):
        with open(data_path, 'r') as f:
          assignments_lut_cache = json.load(f)
          return assignments_lut_cache


  source_modules = get_modules(source_course_id)
  modules = get_modules(course_id)

  #we have to create missing assignments as part of getting assignments lookup table
  count = create_missing_assignments(modules, source_modules, course_id, source_course_id)

  #reload modules after creating assignments
  modules = get_modules(course_id)

  assignments_lut = dict()

  #build assignments from modules by getting assignments in order, discussions in order, and gallery discussion in order

  for source_module in source_modules:
    items = source_module["items"]

    #skip non-week modules
    number = get_source_module_number(source_module)
    name = get_source_module_title(source_module)
    if not number:
      continue

    module = find_new_module_by_number(number, modules)
  
    source_assignments = list ( filter( lambda item: item["type"] == "Assignment", source_module["items"]) )
    assignments = list( filter( lambda item: item["type"] == "Assignment", module["items"]) )
  
    discussions = list( filter( lambda item: item["type"] == "Discussion", module["items"]) )
    source_discussions = list ( filter( lambda item: item["type"] == "Discussion", source_module["items"]) )
  
    source_gallery_discussions = remove_gallery_discussions(source_discussions)
    gallery_discussions = remove_gallery_discussions(discussions)

    populate_lookup_table(assignments_lut, assignments, source_assignments)
    populate_lookup_table(assignments_lut, discussions, source_discussions)
    populate_lookup_table(assignments_lut, gallery_discussions, source_gallery_discussions)


  #We also want to associate discussions with their corresponding assignment ID
  discussions = get_paged_data(f"{api_url}/courses/{course_id}/discussion_topics")
  source_discussions = get_paged_data(f"{api_url}/courses/{source_course_id}/discussion_topics")

  discussions_by_ids = dict()
  for discussion in discussions:
    discussions_by_ids[discussion['id'] ] = discussion

  for source_discussion in source_discussions: 
    if not str(source_discussion['id']) in assignments_lut:
      print (f"Skipping {source_discussion['title']}")
      continue

    discussion_info = assignments_lut[ str(source_discussion['id']) ]
    discussion_id = discussion_info['content_id']
    print(f"looking for discussion {discussion_id}")
    discussion = discussions_by_ids[ discussion_id ]
    print(source_discussion['assignment_id'])
    assignments_lut[ str(source_discussion['assignment_id']) ] = discussion

  #save this off both in ram and disk
  assignments_lut_cache = assignments_lut
  with open(data_path, 'w') as f:
    json.dump(assignments_lut, f, indent=2)

  return assignments_lut

def get_rubrics_lookup_table(rubrics, source_rubrics ):
  out = dict()
  for source_rubric in source_rubrics:
    print(source_rubric["title"])
    rubric = next( filter( lambda a: a["title"] == source_rubric["title"], rubrics) ) 
    print(rubric["title"])
    out[ source_rubric["id"] ] = rubric

  return out

def align_rubrics(course_id, source_course_id):
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)
  source_rubric_url = f"{api_url}/courses/{source_course_id}/rubrics?per_page=100"
  rubric_url = f"{api_url}/courses/{course_id}/rubrics?per_page=100"

  source_rubric_response = requests.post(source_rubric_url, headers=headers)
  rubric_response = requests.post(rubric_url, headers=headers)


  source_rubrics = get_paged_data(source_rubric_url)
  rubrics = get_paged_data(rubric_url)

  rubrics_lut = get_rubrics_lookup_table(rubrics, source_rubrics)
  for source_rubric in source_rubrics:
    try:

      response = requests.get(f"{api_url}/courses/{source_course_id}/rubrics/{source_rubric['id']}", headers=headers, data={ "include[]" : "associations"} )
      assert response.ok, f"problem getting rubric {source_rubric['id']} : {source_rubric['description']}"
      source_rubric_data = response.json()
      for association in source_rubric_data["associations"]:
        source_item_id = association["association_id"]
        print(source_item_id)
        if association["association_type"] == "Assignment":
          rubric = rubrics_lut[ source_rubric["id"] ]
          assert rubric, f"Rubric {source_rubric['description']} not found in new course. You may need to import rubrics."

          print("assigning...")
          assignment = assignments_lut[str(source_item_id)]
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

          assert response.ok
          url = f"{api_url}/courses/{course_id}/rubrics/{rubric['id']}"



    except Exception as e:
      print("---ERROR---")
      print(f"Problem with {source_rubric['id']}...")
      print(type(e))
      print(e.args)
      raise e
      print("---/ERROR---")



def align_assignments(course_id, source_course_id):
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)
  modules = get_modules(course_id)
  source_modules = get_modules(source_course_id)
  source_id_to_id_lut = dict()

  files_lut = get_files_lookup_table(course_id, source_course_id)
  update_assignment_categories(course_id, source_course_id)


  for source_module in source_modules:
    items = source_module["items"]

    #skip non-week modules
    number = get_source_module_number(source_module)
    name = get_source_module_title(source_module)
    if not number:
      continue

    module = find_new_module_by_number(number, modules)
  
    source_assignments = list ( filter( lambda item: item["type"] == "Assignment", source_module["items"]) )
    assignments = list( filter( lambda item: item["type"] == "Assignment", module["items"]) )
  
    source_discussions = list ( filter( lambda item: item["type"] == "Discussion", source_module["items"]) )
    source_gallery_discussions = remove_gallery_discussions(source_discussions)

    discussions = list( filter( lambda item: item["type"] == "Discussion", module["items"]) )
    gallery_discussions = remove_gallery_discussions(discussions)

    discussion_number = 1
    gallery_discussion_number = 1
    assignment_number = 1

    handle_items(course_id, source_course_id, module, gallery_discussions, source_gallery_discussions, handle_discussion, f"Week {number} " +  "Gallery Discussion {number}- {name}")
    handle_items(course_id, source_course_id, module, discussions, source_discussions, handle_discussion, f"Week {number} " + "Discussion {number}- {name}")
    handle_items(course_id, source_course_id, module, assignments, source_assignments, handle_assignment, f"Week {number} " + "Assignment {number}- {name}")



def get_new_file_url(src, course_id, source_course_id):
  files_lut = get_files_lookup_table(course_id, source_course_id)
  file_match = re.search(r"files\/([0-9]+)", src)
  if file_match:
    groups = file_match.groups()
    source_id = groups[0]
    if source_id in files_lut:
      new_file = files_lut[source_id]
      url = new_file['url']
      url = re.sub('verifier(.*)&?', '', url)  
      if "wrap" in src:
        url = url + "wrap=1"
      data_url = re.sub(html_url, api_url, new_file['url'])
      return url, data_url

  return None, None

def get_new_assignment_url(src, course_id, source_course_id):
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)

  file_match = re.search(r"(assignments|discussion_topics)\/([0-9]+)", src)
  if file_match:
    type_url_part = file_match.groups()[0]
    print(type_url_part)
    groups = file_match.groups()
    source_id = groups[1]
    if str(source_id) in assignments_lut:
      new_assignment = assignments_lut[str(source_id)]
      content_id = None
      if 'content_id' in new_assignment:
        content_id = new_assignment['content_id']
      else:
        content_id = new_assignment['id']
      url = f"{html_url}/courses/{course_id}/{type_url_part}/{content_id}"
      data_url = url

      return url, data_url

  return None, None

def get_new_page_url(src, course_id, source_course_id):
  #naively update link by keeping same path and updating course if
  page_match = re.search(fr"courses\/{source_course_id}/pages\/(.+)", src)
  print(f"Remapping page {src}")
  if page_match:
    groups = page_match.groups()
    path = groups[0]
    url = re.sub(f'/courses/.*', f'/courses/{course_id}/pages/{path}', src)
    data_url = re.sub('/api/v1', '', url)
    return url, data_url
  return None, None

def update_links(soup, course_id, source_course_id):
  files_lut = get_files_lookup_table(course_id, source_course_id)
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)
  print("Updating Links")
  #handle a tags
  links = soup.find_all('a')
  for link in links:
    if not link.has_attr('href'):
      print("No Href in Link")
      continue

    #skip outside links
    if not "instructure" in link['href']: 
      continue

    print(link['href'])

    #see if we can turn it into a new page, file, or assignment url
    for func in [get_new_file_url, get_new_assignment_url, get_new_page_url]:
      new_url, data_url = func(link["href"], course_id, source_course_id)
      if new_url:
        source_url = link['href']
        link["href"] = new_url
        link["data_api_endpoint"] = data_url
        print(f'{source_url}\nmapped to\n{link["href"]}')
        break

  #handle images
  imgs = soup.find_all('img')
  for img in imgs:
    if not img.has_attr('src'):
      continue
    if not 'instructure' in img['src']:
      continue
    new_url, data_url = get_new_file_url(img["src"], course_id, source_course_id)
    
    if new_url:
      source_url = img['src']
      img["src"] = new_url
      img["data_api_endpoint"] = data_url
      print(source_url + " ---> " + img["src"])


def handle_items(course_id, source_course_id, module, items, source_items, handle_func, format_title):
  i = 0

  handled = []

  for source_item in source_items:
    item = items[i]
    handled.append(item)
    course_id_regex = re.compile(f'{api_url}/courses/(\d+)/(assignments|discussion_topics)/(\d+)')
    match = course_id_regex.match(items[0]["url"])
    source_match = course_id_regex.match(source_item["url"])


    print(f"Parsing {source_item['title']} into {item['title']}")

    assert match, f"regex broken for string {items[0]['url']}"
    assert source_match, f"regex broken for string {source_item['url']}"
    item_id = match.group(3)
    source_item_id = source_match.group(1)

    url = item["url"]
    source_url = source_item["url"]
    response = requests.get(url, headers=headers)
    assert response.ok, json.dumps(response.json(), indent=2)

    source_response = requests.get(source_url, headers=headers)
    assert source_response.ok, json.dumps(response.json(), indent=2)

    item = response.json()
    source_item = source_response.json()

    handle_func(item, source_item, course_id, source_course_id, url, i, len(source_items), format_title)
    i = i + 1

  for item in items:
    if not item in handled:
      remove_item_from_module(item, module, course_id)

def remove_item_from_module(item, module, course_id):
  url = f"{api_url}/courses/{course_id}/modules/{item['module_id']}/items/{item['id']}"
  print(url)
  response = requests.delete(url, headers=headers)
  print("DELETING")


#takes in the new item and old item, and formats the info from the old page into the new item
def handle_discussion(item, source_item, course_id, source_course_id, put_url, index, total, format_title):

  files_lut  = get_files_lookup_table(course_id, source_course_id)
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)

  source_name = source_item["title"]
  name = item["title"]

  #sets the display number of the discussion (e.g. discussion 2) only if there are more than one of them
  display_number = ""
  if total > 1:
    display_number = f"{index + 1} "

  #split the header into components for use later
  new_name, title, subhead = get_new_name_title_and_subhead(source_name, format_title, display_number)
  print(f"migrating {source_name} to {new_name}")


  #save off a backup of this data
  base_folder = "course_data"
  folder_path = os.path.join(os.getcwd(), base_folder, str(course_id), "discussions", str(item['id']))
  ensure_directory_exists(folder_path)
  list_of_files = glob.glob(f'{folder_path}/*.json')
  filename = f"{item['id']}_{len(list_of_files)}.json"

  with open(os.path.join(folder_path, filename) , 'w') as f:
    json.dump(item, f, indent=2)


  source_body = source_item["message"]
  body = item["message"]

  source_soup = BeautifulSoup(source_body, 'lxml')
  soup = BeautifulSoup(body, 'lxml')


  contents = find_source_assignment_content(source_soup)

  #put everything in the migration insertion section
  insert_el = soup.find('div', id="migrate_insert")
  if not insert_el:
    insert_el = soup.new_tag('div', id="migrate_insert")
    soup.body.insert(len(soup.body.contents), insert_el)

  #replace_header
  replace_header(soup, title, subhead)

  if contents:
    insert_el.clear()
    insert_el.append(contents)

  replace_rubric_link(soup, course_id, source_course_id, item)
  update_links(soup, course_id, source_course_id)

  response = requests.put(put_url, headers=headers, data= {
    "title" : new_name,
    "message" : postprocess_soup(soup)
    })


def replace_rubric_link(soup, course_id, source_course_id, item):
  print(item)
  rubric_button = soup.find('p', class_="cbt-rubric-btn")
  if not rubric_button:
    print("Rubric button not found", item['title'])
    return False

  link = rubric_button.find('a')
  if not link:
    print("Link in rubric button not found", item['title'])
    assignments_lut = get_assignments_lookup_table(course_id, source_course_id)
    assignment = next( filter( lambda x: 'assignment_id' in x and x['id'] == item['content_id'], assignments_lut), None )


#takes in the new item and old item, and formats the info from the old page into the new item
def handle_assignment(item, source_item, course_id, source_course_id, put_url, index, total, format_title):

  files_lut  = get_files_lookup_table(course_id, source_course_id)
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)

  source_assignment = get_assignment(source_course_id, source_item['id'])
  destination_assignment = get_assignment(course_id, item['id'])
  source_name = source_item["name"]
  name = item["name"]

  display_number = ""
  if total > 1:
    display_number = f"{index + 1} "

  new_name, title, subhead = get_new_name_title_and_subhead(source_name, format_title, display_number)
  print(f"migrating {source_name} to {new_name}")

  source_body = source_item["description"]
  source_soup = BeautifulSoup(source_body, 'lxml')

  #save off a backup of this data
  base_folder = "course_data"
  folder_path = os.path.join(os.getcwd(), base_folder, str(course_id), "assignments", str(item['id']))
  ensure_directory_exists(folder_path)
  list_of_files = glob.glob(f'{folder_path}/*.json')
  filename = f"{item['id']}_{len(list_of_files)}.json"

  with open(os.path.join(folder_path, filename) , 'w') as f:
    json.dump(item, f, indent=2)


  body = item["description"]
  soup = BeautifulSoup(body, 'lxml')

  replace_header(soup, title, subhead)
  #insert the contents of the old page into the bottom of the new page
  contents = find_source_assignment_content(source_soup)

  insert_el = soup.find('div', id="migrate_insert")
  if not insert_el:
    insert_el = soup.new_tag('div', id="migrate_insert")
    soup.body.insert(len(soup.body.contents), insert_el)

  insert_el.clear()
  if contents:
    insert_el.append(contents)

  #update links on the whole thing
  update_links(soup, course_id, source_course_id)

  new_text = postprocess_soup(soup)

  payload = {
    "assignment[submission_types][]" : source_assignment['submission_types'],
    "assignment[name]" : new_name,
    "assignment[description]" : new_text,
    "assignment[published]" : True,
  }
  print('----------------------')

  print(source_assignment['submission_types'])
  response = requests.put(put_url, headers=headers, data= payload)
  if not response.ok:
    print(response.json())
    print(json.dumps(payload, indent=2))
  print(response)


def add_to_payload_if_exists_in_source(key, wrapper, source, payload):
  print(key)
  if key in source:
    print(source[key])
    payload[wrapper.format(key=key)] = source[key]

def get_assignment(course_id, assignment_id):
  url = f"{api_url}/courses/{course_id}/assignments/{assignment_id}"
  response = requests.get(url, headers=headers)
  if response.ok:
    return response.json()
  else:
    return False

def find_source_assignment_content(soup):
  contents = soup.find('div', class_="column")
  if not contents:
    contents = soup.body
  return contents

def get_new_name_title_and_subhead(source_name : str, format_title : str, display_number : int):
  title = re.sub(r'^.*[:-]\W+', '', source_name)
  subhead = re.sub(r'[:-].*', '', source_name)
  new_name = f'{subhead} - {title}'

  return new_name, title, subhead

def replace_header(soup, title, subhead):
  head = soup.h1
  head.string.replace_with(title)

  subhead_el = soup.find('h1').find_previous_sibling('p')
  subhead_el.string.replace_with(subhead)


def populate_lookup_table(lut, items, source_items):
  i = 0
  if len(source_items) > len(items):
    raise Exception("Number of items in new module is fewer than items in old module")
  for source_item in source_items:
    item = items[i]
    i = i + 1
    lut[str(source_item["content_id"]) ] = item

def remove_assignments_and_discussions_not_in_modules(course_id, source_course_id):
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
  if len(assignments_to_delete) > 0 and tk.messagebox.askyesno(message=f"Do you want to delete the following assignments?\n{assignments_string}"):
    for assignment in assignments_to_delete:
      result = requests.delete(f"{api_url}/courses/{course_id}/assignments/{assignment['id']}", headers=headers) 
      print(result)


  discussions_string = '\n'.join( list( map( lambda item: item["title"], discussions_to_delete)))
  print(discussions_to_delete)
  if len(discussions_to_delete) > 0 and tk.messagebox.askyesno(message=f"Do you want to delete the following discussions?\n{discussions_string}"):
    for discussion in discussions_to_delete:
      result = requests.delete(f"{api_url}/courses/{course_id}/discussion_topics/{discussion['id']}", headers=headers) 
      print(result)

def remove_gallery_discussions(discussions, remove_introduction = True):
  print(discussions)
  gallery_discussions = []
  to_remove = []
  for discussion in discussions:
    #just throw away introductions
    if remove_introduction and  discussion["title"] == "Introductions":
      print("REMOVING INTRODUCTIONS")
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

  response = requests.post(url, headers=headers, data = payload)
  if not response.ok:
    raise response.raise_for_status()

  return item

def get_source_module_number(module):  
    title_words = module["name"].split(" ")
    if ( "week" in title_words[0].lower()):
      return title_words[1]
    return False

def get_source_module_title(module):  
    #if the module name is "Week X" return the name of the subheader
    title_words = module["name"].split(" ")
    if ( "week" in title_words[0].lower()):
      return module["items"][0]["title"]

    #if the module name is not "Week X" just return the full module name
    return module["name"]

def find_new_module_by_number(number, modules):
 return next( filter ( lambda module: f"Module {number}" in module["name"], modules) )

def update_weekly_overviews(course_id, source_course_id):

  source_modules = get_modules(source_course_id)
  modules = get_modules(course_id)

  for source_module in source_modules:
    print(source_module["name"])
    title_words = source_module["name"].split(" ")
    items = source_module["items"]
    if ("week" in title_words[0].lower()):


      i = int(title_words[1])
      module_name = source_module ['items'][0]["title"]

      module = next( filter ( lambda module: f"Module {i}" in module["name"], modules) )

      set_module_title(course_id, module["id"], f"Module {i} - {module_name}".title())
  
      source_overview_page_info = next(filter(lambda item: "overview" in item["title"].lower() and item["type"] == "Page", items))
      source_lo_page_info = next(filter(lambda item: "learning objectives" in item["title"].lower(), items))

      source_overview_page = get_page_by_url (source_overview_page_info["url"])
      source_lo_page = get_page_by_url (source_lo_page_info["url"])
      overview_page = get_page_by_url (f"{api_url}/courses/{course_id}/pages/week-{i}-overview")

      source_overview_soup = BeautifulSoup( preprocess_html(source_overview_page["body"]), 'lxml')
      source_lo_soup = BeautifulSoup( preprocess_html(source_lo_page["body"]), 'lxml')

      #grab the list of learning objectives from the page
      learning_objectives = source_lo_soup.find('ul')
      if not learning_objectives:
        learning_objectives = source_lo_soup.find("ol")

      learning_objectives = str(learning_objectives)

      update_links(source_overview_soup, course_id, source_course_id)
      description_box = source_overview_soup.find("div", class_="column")
      description_elements = None
      if description_box:
        description_elements = list(description_box.children)
      else:
        description_elements = source_overview_soup.find_all('p')


      description = "\n".join( 
        map(lambda tag: str(tag), description_elements)
      )

      new_page_body = new_overview_page_html(course_id, source_course_id, overview_page["body"], module_name, description, learning_objectives)

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

def new_overview_page_html(course_id, source_course_id, overview_page_body, title, description, learning_objectives):
  body = overview_page_body 
  soup = BeautifulSoup(body, "lxml")
  contents = soup.find_all("div", class_ = "content")
  contents[0].string = "[Insert text]"
  contents[1].string = "[insert weekly objectives, bulleted list]"

  update_links(soup, course_id, source_course_id)
  body = postprocess_soup(soup)

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

def update_syllabus_and_overview(course_id, source_course_id):

  source_page = get_syllabus(source_course_id)
  new_page = get_syllabus(course_id)

  syllabus_banner_url = get_file_url_by_name(course_id, "Module 1 banner (7)")

  is_course_grad = not source_page.find(string=re.compile("Poor, but Passing"))
  if is_course_grad:
    set_course_grad(course_id)

  title = find_syllabus_title(source_page)
  description_section = get_section(source_page, re.compile(r'.*description', re.IGNORECASE))
  learning_objectives_section = get_section(source_page, re.compile(r'outcomes', re.IGNORECASE))
  if not learning_objectives_section:
    learning_objectives_section = get_section(source_page, re.compile(r'objectives', re.IGNORECASE))
  textbook_section = get_section(source_page, re.compile(r'.*textbook[:]?', re.IGNORECASE))
  week_1_preview = get_week_1_preview(course_id, source_course_id)

  term = GRAD_TERM_NAME if is_course_grad else UG_TERM_NAME
  dates = GRADE_TERM_DATES if is_course_grad  else UG_TERM_DATES

  update_syllabus(course_id, syllabus_banner_url, term, dates, learning_objectives_section, description_section, title, week_1_preview, textbook_section, is_course_grad)

  #update the home page with the title we grabbed
  course_title = None
  course_code = None
  match = re.search(r'.*(\w{4}\s*\d{3})\s*[:-]?\s*(.*)', title)
  if match:  
    groups = match.groups()
    course_title = groups[1]
    course_code = re.sub(r'\s+','', groups[0])


  update_home_page(course_id, source_course_id, course_code, course_title)
  update_course_overview(course_id, source_course_id, learning_objectives_section, description_section, textbook_section)


def set_course_grad(course_id):


  print("Setting grad course grading standards")

  url = f"{api_url}/accounts/{ACCOUNT_ID}"
  account = requests.get(url, headers=headers).json()


  url = f"{api_url}/accounts/{account['root_account_id']}/grading_standards"
  grading_standards = get_paged_data(url)
  print(grading_standards)
  grad_standard = next( filter( lambda scheme: GRAD_SCHEME_NAME.lower() in scheme['title'].lower(), grading_standards), None)
  assert grad_standard, f"Cannot find {GRAD_SCHEME_NAME}"
  response = requests.put(f"{api_url}/course/{course_id}", headers=headers, data={
    "course[grading_standard_id]" : grad_standard['id']

    })
  print(response)



def update_syllabus(course_id, syllabus_banner_url, term, dates, learning_objectives_section, description_section, title, week_1_preview, textbook_section, is_course_grad):
  #format syllabus template from disk
  try:
    with open("syllabus_template.html", 'r') as f:
      template = f.read()
      text = template.format(
        banner_url = syllabus_banner_url,
        course_id = course_id,
        term_code = term,
        term_dates = dates,
        course_outcomes = stringify_section(learning_objectives_section),
        course_description = stringify_section(description_section),
        course_title = title,
        week_1_learning_materials = week_1_preview,
        textbook = stringify_section(textbook_section),
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
    raise e

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
      "course[syllabus_body]" : str(submit_soup)
    }
  )
  print(response.status_code)


def update_course_overview(course_id, source_course_id, learning_objectives_section, description_section, textbook_section):

  #update overview
  modules = get_modules(course_id)

  overview_module = next(filter(lambda module: module["position"] == 1, modules))
  page_id  = overview_module['items'][0]['page_url']
  url = f"{api_url}/courses/{course_id}/pages/{page_id}"

  response = requests.get(url, headers=headers)
  print(response.status_code)
  overview_page = response.json()

  overview_html = overview_page["body"]
  og_ov_soup = BeautifulSoup(preprocess_html(overview_html), "lxml").body
  overview_banner_img = og_ov_soup.find("div", class_="cbt-banner-image").find('img')
  overview_banner_url = overview_banner_img["src"]

  #get assignment groups
  url = f"{api_url}/courses/{source_course_id}/assignment_groups"
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
        course_outcomes = stringify_section(learning_objectives_section),
        course_description = stringify_section(description_section),
        table_body = table_body,
        textbook = stringify_section(textbook_section),
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
      "wiki_page[body]" : str(submit_soup)
    }
  )  

def update_home_page(course_id, source_course_id, course_code, course_title):
  #set to template defaults in case we don't find them so we don't break the templating
  if not course_code:
    course_code = '[Code and #]'

  if not course_title:
    course_title = '[Course title]'

  print(f'updating {course_code} : {course_title}')

  source_url = f"{api_url}/courses/{source_course_id}/pages/course-introduction"
  response = requests.get(source_url, headers=headers)
  if not response.ok:
    raise Exception("There was a problem getting course introduction from source course")

  source_text = response.json()["body"]
  source_soup = BeautifulSoup(source_text)

  #we're just going to guess that the contents of the first table cell are the learning materials
  cell = source_soup.find('td')
  description = "[Insert course introduction - so long as it is distinct from description and speaks directly to the student]"
  if cell:
    divs = cell.find_all('p')
    if divs:
      description = '\n'.join( list( map(lambda x: str(x), divs) ) )

  dest_url = f"{api_url}/courses/{course_id}/pages/home"
  response = requests.get(dest_url, headers = headers)
  if not response.ok:
    raise Exception("There was a problem finding destination home page")

  print(course_code)
  dest_page = response.json()
  dest_text = dest_page['body']
  dest_text = re.sub(r'\[Insert course introduction.*student\]', description, dest_text)
  dest_text = re.sub(r'\[Code and #\]', course_code, dest_text)
  dest_text = re.sub(r'\[Course title\]', course_title, dest_text)


  print(dest_text)

  response = requests.put(f"{api_url}/courses/{course_id}/pages/{dest_page['page_id']}", headers=headers, data={
    "wiki_page[body]" : dest_text
  })
  print(response.json())


def stringify_section(section):
  if section:
    out = "\n".join(map(lambda p: str(p), section))
    return out

  return "<p style='background-color: red; color: white'>Not Found</p>"

def get_syllabus(course_id):
  url = f"{api_url}/courses/{course_id}?include[]=syllabus_body"
  response = requests.get(url, headers=headers)
  content = response.json()
  return BeautifulSoup(preprocess_html(content["syllabus_body"]), "lxml")

def find_syllabus_title(soup):
  print(soup.prettify())
  header = soup.find("strong", string=re.compile("course number and title", re.IGNORECASE))
  title_p = header.find_parent("p")
  if not title_p:
    title_p = header.find_parent("h4")
  if not title_p:
    title_p = header.find_parent("h3")
  if not title_p:
    title_p = header.find_parent("h2")
    assert header, "Syllabus title not found"
  header.decompose()
  return title_p.text

def get_section(soup, header_pattern):

  strategies = [
    gs_strat_until_headerlike
  ]

  for strategy in strategies:
    result = strategy(soup, header_pattern)
    if result:
      return result

  print("section not found")
  return False

def gs_strat_until_headerlike(soup, header_pattern):
  header = get_section_header(soup, header_pattern)
  print("header", header)
  if not header:
    print("header not found", header_pattern)
    return False
  parent = header.parent
  print("parent", parent.name)
  paragraphs = []

  el =  header.find_next_sibling()

  while el and el.name != "h4" and not len(list(el.find_all('strong', string=re.compile(r':')))) > 0 and not len(el.text) < 5:
    print(el.name)
    paragraphs.append(el)
    el = el.find_next_sibling()

  return paragraphs

def get_section_header(soup, header_pattern):
  print(f"Getting Section Header {header_pattern}")

  # gsh_funcs are various ways of finding headers, so we can apply them in order
  header_strategies = [
    gsh_func_h4,
    gsh_func_strong,
  ]
  for strategy in header_strategies:
    header = strategy(soup, header_pattern)
    #if strategy has succeeded, we can leave
    if header:
      return header

def gsh_func_h4(soup, header_pattern):
  headers = soup.find_all("h4")
  for header in headers:
    print(header, header_pattern)
    if re.search(header_pattern, str(header)):
      print("Found ", header)
      return header

def gsh_func_strong(soup, header_pattern):
  print(soup)
  headers = soup.find_all("strong")
  for header in headers:
    print(str(header))
    if re.search(header_pattern, str(header)):
      print("Found ", header)
      return header.parent


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


def get_week_1_preview(course_id, source_course_id):

    source_lm_url = f"{api_url}/courses/{source_course_id}/pages/week_1_learning_materials"
    lm_response = requests.get(source_lm_url, headers=headers)

    print(lm_response)

    lm_page = lm_response.json()
    lm_soup = BeautifulSoup(preprocess_html(lm_page["body"]), "lxml")

    h4 = lm_soup.find("h4")
    learning_materials = None
    if h4:
      learning_materials = list(h4.next_siblings)
    else:
      section = get_section(lm_soup, re.compile("Please read (and watch )?the following materials:", re.IGNORECASE))
      learning_materials = list(section)

    iframe = lm_soup.find("iframe")
    youtube_iframe_source = iframe["src"] if iframe else "#"
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

    update_links(temp_soup, course_id, source_course_id)


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

  source_lm_url = response.json()[-1]["url"]
  return source_lm_url
def update_learning_materials_cl(course_id : str, source_course_id: str):
  force = False
  start_index = 1
  end_index = 8
  if 'lm_reset' in sys.argv:
    force = True

  if "lm" in sys.argv and sys.argv.index('lm') + 1 < len ( sys.argv ):
    next_arg = sys.argv[ sys.argv.index('lm') + 1 ]
    if str( next_arg ).isdigit():
      start_index = int( next_arg )
      end_index = int( next_arg )

  update_learning_materials(course_id, source_course_id, start_index, end_index, force)


def update_learning_materials(course_id : str, source_course_id : str, start_index : int = 1, end_index : int = 8, reset_page : bool = False):
  assignments_lut = get_assignments_lookup_table(course_id, source_course_id)
  files_lut = get_files_lookup_table(course_id, source_course_id)

  print("Updating Learning Materials")
  for i in range(start_index, end_index + 1):
    source_url = f"{api_url}/courses/{source_course_id}/pages/week_{i}_learning_materials"
    new_url = f"{api_url}/courses/{course_id}/pages/week_{i}_learning_materials"
    #source_url = get_latest_lm_backup(course_id, i)

    print(f"copying from {source_url} to {new_url}")

    if reset_page:
      print("Resetting transcript page")
      result = requests.post(f"{new_url}/revisions/1", headers=headers)
      print(result)

    source_page_response = requests.get(source_url, headers=headers)
    if not source_page_response.ok:
      print(f"source page not found {i}")
      continue
    source_page = source_page_response.json()

    new_page_response = requests.get(new_url, headers=headers)
    if not new_page_response.ok:
      print(f"new page not found {i}")
      continue
    new_page = new_page_response.json()

    source_soup = BeautifulSoup(preprocess_html(source_page["body"]), "lxml")
    new_soup = BeautifulSoup (new_page["body"], "lxml")
    
    #handle first frame youtube links
    source_iframes = list( source_soup.find_all("iframe") )
    new_iframes = new_soup.find_all("iframe")
    print(source_iframes)
    if len ( source_iframes ) > 0:
      youtube_iframe_source = source_iframes[0]["src"]
      new_iframes[0]["src"] = youtube_iframe_source
    else:
      new_soup.find("iframe").findParent('div', { 'class' : 'content' }).find('h2').string = "No Videos Found"

    source_header = source_soup.find("h4")
    learning_materials = None
    if source_header:
      learning_materials = list(source_header.next_siblings)
    else:
      learning_materials = get_section(source_soup, re.compile("Please read (and watch )?the following materials:", re.IGNORECASE))
    
    cols = source_soup.find_all("div", {'class':"column"})


    transcripts_and_slides = []
    if len(cols) > 1:
      transcripts_and_slides = cols[1].find_all("a")
    else:
      transcripts_and_slides = source_soup.find_all('a')

    print(transcripts_and_slides)

    transcripts = list( filter(lambda el: "transcript" in el.text.lower(), transcripts_and_slides))
    slides = list( filter(lambda el: "slides" in el.text.lower(), transcripts_and_slides))

    #save slides and transcript buttons
    buttons = new_soup.find_all("p", { "class" : "cbt-button"})
    slides_buttons = []
    transcript_buttons = []

    for button in buttons:
      if button.find("a", string=re.compile("Slides",re.IGNORECASE)):
        slides_buttons.append( button.find("a", string=re.compile("Slides",re.IGNORECASE)) )
      if button.find("a", string=re.compile("Transcript", re.IGNORECASE)):
        transcript_buttons.append( button.find("a", string=re.compile("Transcript", re.IGNORECASE)) )

    slides_count = 0
    transcripts_count = 0
    source_transcript_button = None

    #clean up secondary media boxes
    secondary_media_boxes = get_secondary_media_boxes(new_soup)

    #if there are more than one old iframe, we're gonna make secondary media boxen to match, if we have a secondary media box to go on
    total_needed_boxes = len(source_iframes) - 1
    if len( source_iframes ) > 1 and len ( secondary_media_boxes ) > 0:
        boxes_to_add = total_needed_boxes - len (secondary_media_boxes)
        last_box = secondary_media_boxes[-1]
        if boxes_to_add > 0:
          new_box = copy.copy(last_box)
          last_box.insert_after(new_box)
          last_box = new_box


    handle_lm_secondary_media_boxes(new_soup, source_iframes, transcripts, slides, transcript_buttons, slides_buttons)

    #make a new accordion and put all the learning materials into it IF this accordion is a template
    add_lm_import_accordion(new_soup, transcripts, slides, learning_materials)

    #update links
    update_links(new_soup, course_id, source_course_id)

    #save changes
    response = requests.put(f'{api_url}/courses/{course_id}/pages/{new_page["page_id"]}', 
      headers = headers,
      data = {
        "wiki_page[body]" : postprocess_soup(new_soup)
      }
    )
    print(new_page["title"], response.status_code)

def get_secondary_media_boxes(soup):
  secondary_media_boxes = []
  h3s = soup.find_all('h3')
  for h3 in h3s:
    if "secondary media element" in h3.text:
      secondary_media_boxes.append(h3.parent)

  print(secondary_media_boxes)
  return secondary_media_boxes

def clear_all_but_1_lm_button(buttons):
  button_count = len(buttons)

  if button_count > 1:
    for i in range(1, button_count):
      button = buttons[i]
      button.parent.parent.decompose()


def handle_lm_secondary_media_boxes(soup : object, source_iframes: list, transcripts : list, slides : list, transcript_buttons : list, slides_buttons : list):
  total_needed_boxes = len(source_iframes) - 1
  secondary_media_boxes = get_secondary_media_boxes(soup)
  print(secondary_media_boxes)
  #set video urls across media boxes, removing them if they have no equivalents
  for i in range(0, len(secondary_media_boxes)):
    box = secondary_media_boxes[i]
    if i <= total_needed_boxes - 1:
      box.find("iframe")['src'] = source_iframes[i + 1]["src"]
    else:
      box.decompose()


  secondary_media_boxes = get_secondary_media_boxes(soup)
  print("T", transcripts)
  print("S", slides)


  remaining_transcripts = handle_first_lm_button(transcripts, transcript_buttons, 'Transcript')  
  remaining_slides = handle_first_lm_button(slides, slides_buttons, 'Slides')  

  print("RT", remaining_transcripts)
  print("RS", remaining_slides)

  #if there aren't any slides just kill the button
  if not slides:
    for button in slides_buttons:
      button.parent.decompose()

  i = 0
  if secondary_media_boxes:
    print(secondary_media_boxes)
    for box in secondary_media_boxes:
      handle_secondary_media_element_link(box, i, soup, remaining_transcripts, "transcript")
      handle_secondary_media_element_link(box, i, soup, remaining_slides, "slide")
      i = i + 1

def handle_first_lm_button(items : list, buttons : list, button_text : str):
  if len(items) > 0:
    source_button = buttons[0]
    source_button["body"] = f"Transcript"
    source_button["href"] = items[0]["href"]
    out = items.copy()
    out.remove(items[0])
    return out
  else:
    return items.copy()

def handle_secondary_media_element_link(box : object, number : int, soup: object, items : list, type_ : str):
  if number < len(items):
    item = items[number]
    link = box.find('a', id=f"{type_}_link_{number}")
    if not link:
      link = soup.new_tag('a', string=type_.capitalize(), id=f"{type_}_link_{number}")
      p = box.find('p')
      p.insert(0, link)

    link["href"] = item["href"]
    link.string = type_.capitalize()

def add_lm_import_accordion(soup : object, transcripts : list, slides : list, learning_materials : list):
  accordion_list = list(soup.find_all("div", class_='auto-add'))
  accordion = None
  if accordion_list and len(accordion_list) > 0:
    accordion = accordion_list[-1]
  if not accordion:
    accordion = soup.find("div", class_="cbt-accordion-container")

    if accordion.find(text=re.compile("Title for first category of LMs", re.IGNORECASE)):
      print("adding Learning Materials")
      new_content = copy.copy(accordion)
      accordion.parent.append(new_content)
      new_content['class'].append('auto-add')
      content = new_content.find("div", class_="cbt-answer")
      for transcript in transcripts:
        content.append(transcript)
      for slide in slides:
        content.append(slide)
      for el in learning_materials:
        content.append(el)
  else:
    content = accordion.find("div", class_="cbt-answer")
    content.clear()
    for transcript in transcripts:
      content.append(transcript)
    for slide in slides:
      content.append(slide)
    for el in learning_materials:
      content.append(el)

    return soup

def strip_spans(text):
  soup = BeautifulSoup(text, 'lxml')
  for span in soup.find_all("span"):
    span.replaceWithChildren()
  return get_body_html  ( soup )

def preprocess_html(text):
  soup = BeautifulSoup(text, 'lxml')
  return get_body_html(soup)


def get_body_html(soup):
  children = soup.body.findChildren (recursive   = False)
  return '\n'.join( (list( map (lambda child: str(child), children  ))) )

def postprocess_soup(soup, remove_styling_span=False):
  for span in soup.find_all("span"):
    if remove_styling_span or (not span.has_attr('style') and not span.has_attr('class')):

      if span.parent:
        span.replaceWithChildren()

  text = get_body_html(soup)

  text = re.sub(r'(<a[^>]*>)\s+', r'\1', text)
  text = re.sub(r'\s+</a>', r'</a>', text)
  text = re.sub(r'(<span[^>]*>)\s+', r'\1', text)
  text = re.sub(r'\s+(</span>)', r'</span>', text)

  text = re.sub(r'(\w)(<a[^>]*>\w)', r'\1 \2', text)
  text = re.sub(r'(\w</a>)(\w)', r'\1 \2', text)

  return text

def get_paged_data(url, headers=headers):
  response = requests.get(url, headers=headers)
  try:
    out = response.json()
  except:
    print(url)
    print(response)
  next_page_link = "!"
  while len(next_page_link) != 0:
    if not "Link" in response.headers:
      break
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

  return out

def update_assignment_dates():
  assignments = get_paged_data(f"{api_url}/courses/{course_id}/assignments?include=due_at")
  update_date_data = []
  for assignment in assignments:
    print(assignment["due_at"])
    due_at = datetime.datetime.fromisoformat(assignment["due_at"])
    due_at = due_at + datetime.timedelta(days=offset)
    response = requests.put(f"{api_url}/courses/{course_id}/assignments/{assignment['id']}",
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


main()