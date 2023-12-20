"""Summary

Attributes:
    ACCOUNT_ID (int): The main account ID of the
        unity account where student courses are places
    account_ids (dict): A dictionary of account ids by account name
    accounts (list): A list of all accounts
    api_token (str): A global variable holding the api access token
    api_url (str): A global variable holding the api url
    browser_button (bool): A button that opens several browser windows
    default_profile_url (str): A url to the default profile image
    email_button (bool): A button that tries to email professors
        associated with courses
    headers (dict): a global variable holding the header used in requests
    html_url (str): A base url for the site
    instructor_course_id (int): A link to the course ID for instructors
    live_headers (dict): headers for the live site.
        Only used to read relevant data when testing
    live_url (str): A url to the live site even when testing
    profile_assignment_id (TYPE): The ID of the assignment
        where user profiles are kept
    profile_pages_course_id (TYPE): The course ID of
        the course with all the faculty pages
    ROOT_ACCOUNT_ID (TYPE): The account ID for the rootmost unity Account
    syllabus_replacements (list): A list of { find, replace} dicts
        where find and replace are paired regexes of re.search calls
        on the syllabus text to replace text

Deleted Attributes:
    log_filename (str): A file to log logs to. Not currently used.
    log_string (str): The opening string of the log
    CONSTANTS_FILE (str): The path to the constants file
    url (TYPE): Description
    max_profile_image_size (int): The max width of profile images to scale
        downloaded profile images to
"""

import time
import traceback
import re
from bs4 import BeautifulSoup
import docx
import sys
import requests
import urllib.parse
import zipfile
import os
import json
import webbrowser
import datetime
import win32com.client as win32
import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog
from PIL import Image


CONSTANTS_FILE: str = 'constants_test.json'
max_profile_image_size: int = 400
# Open the file and read the contents
with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)

# save the api key
api_token: str = constants["apiToken"]
api_url: str = constants["apiUrl"]
html_url: str = re.sub('/api/v1', '', constants["apiUrl"])

instructor_course_id: int = constants["instructorCourseId"]
profile_assignment_id: int = constants["profileAssignmentId"]
profile_pages_course_id: int = constants["profilePagesCourseId"]

default_profile_url = f"{html_url}/users/9230846/files/156109264/preview"
live_url = constants["liveUrl"]

# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}"}
live_headers = {"Authorization": f'Bearer {constants["liveApiToken"]}'}


accounts = requests.get(f'{api_url}/accounts', headers=headers).json()
account_ids = dict()
for account in accounts:
    account_ids[account['name']] = account['id']

ACCOUNT_ID = account_ids['Distance Education']
ROOT_ACCOUNT_ID = account_ids['Unity College']


def main():
    """Summary
    """
    root = tk.Tk()
    number = 0
    if len(sys.argv) > 1:
        number = sys.argv[1]
    else:
        number = simpledialog.askinteger(
            "What Course?",
            "Enter the course_id of the blueprint "
            + "(cut the number out of the url and paste here)")

    bp_id = number

    # Create a progress bar
    progress_bar = ttk.Progressbar(
        root,
        orient="horizontal",
        length=200,
        mode="determinate")
    progress_bar.pack()

    label = tk.Label(root, text="Select which steps to perform")
    label.pack()

    bp_course = get_course(bp_id)
    print(bp_course)
    # source_course_id = get_source_course_id(bp_id)
    courses = get_blueprint_courses(bp_id)

    updates = [
        {
            'name': 'update_syllabus',
            'argument': 'syllabus',
            'message': "Do you want to update syllabus language"
            + "in this and any source?"
            + "\nDo this before sync!",
            'func': lambda: [
                update_syllabus(bp_id),
                update_syllabus(get_source_course_id(bp_id))]
        },
        {
            'name': 'remove_lm_annnotations',
            'argument': 'lm',
            'message': "Do you want to remove "
            + f"lm annotations from {bp_course['name']}?",
            'func': lambda: remove_lm_annotations_from_course(bp_course)

        },
        {
            'name': 'lock',
            'argument': 'lock',
            'message': 'Do you want to lock bluprint module items?',
            'func': lambda: lock_module_items(bp_course)
        },
        {
            'name': 'download_profiles',
            'argument': 'download',
            'message': 'Do you want to '
            + ' redownload the latest faculty profiles?',
            'func': lambda: get_faculty_pages(force=True)
        },
        {
            'name': 'sync',
            'message': 'Do you want sync associated courses?'
            + '\nThis could take a sec.',
            'error': 'There was a problem syncing\n{e}',
            'func': lambda: begin_course_sync(
                course=bp_course,
                progress_bar=progress_bar,
                status_label=label),
        },

        {
            'name': 'profiles',
            'argument': 'profiles',
            'message': 'Do you want to update profiles in associated courses?',
            'error': 'There was a problem updating profile pages\n{e}',
            'func': lambda: replace_faculty_profiles(
                bp_course,
                courses,
                root,
                progress_bar),
        },
        {
            'name': 'publish',
            'message': 'Do you want to publish associated courses?',
            'error': 'There was a problem publishing courses\n{e}',
            'func': lambda: publish_courses(
                courses=courses),


        }
    ]

    # Check if the arguments are on the
    # command line and run those options that are
    if len(sys.argv) > 2:
        for update in updates:
            if update['name'] in sys.argv \
                    or 'argument' in update \
                    and update['argument'] in sys.argv:
                update['func']()

    # if we don't have any arguments past the id, go into interactive mode
    else:

        opening_dialog(course=bp_course, updates=updates,
                       window=root, status_label=label)


def opening_dialog(*, window, course, updates, status_label):
    """Summary
    
    Args:
        window (TYPE): Description
        course (TYPE): Description
        updates (TYPE): Description
        status_label (TYPE): Description
    """
    checkboxes = []
    for update in updates:
        boolVar = tk.BooleanVar()
        button = tk.Checkbutton(
            window, text=update['message'],
            onvalue=True,
            offvalue=False,
            variable=boolVar)
        checkboxes.append(button)
        update['run'] = boolVar
        button.pack()

    button = tk.Button(
        master=window,
        text="Run",
        command=lambda: run_opening_dialog(
            window,
            updates,
            status_label))
    button.pack()

    window.mainloop()


def run_opening_dialog(window, updates, status_label):
    """Summary
    
    Args:
        window (TYPE): Description
        updates (TYPE): Description
        status_label (TYPE): Description
    """
    for update in updates:
        try:
            print(update)
            print(update['name'], update['run'].get())
            if update['run'].get():
                status_label.config(text=f"Running {update['name']}")
                window.update()
                print(update)
                update['func']()
        except Exception as e:
            tk.messagebox.showerror(message=update['error'].format(
                e=str(e)) + "\n" + traceback.format_exc())
            print(traceback.format_exc())

    status_label.config(text=f'Finished!')


def generate_email(*, course, courses, constants, emails):
    """Summary
    
    Args:
        course (TYPE): Description
        courses (TYPE): Description
        constants (TYPE): Description
        emails (TYPE): Description
    """
    with open("email_template.html", 'r') as f:
        template = f.read()

    code = course["course_code"][3:]

    example_course_data = get_course(courses[0]['id'])
    print(json.dumps(example_course_data, indent=2))

    start_date = datetime.datetime.fromisoformat(
        example_course_data['term']["start_at"])
    start_date = start_date + datetime.timedelta(days=7)

    email_subject =\
        f'{course["course_code"][3:]} Section(s) Ready Notification'

    email_body = template.format(
        term={
            "name": courses[0]['term_name'],
            "start": start_date.strftime('%B %#d')
        },
        creator={
            "name": "[[YOUR NAME]]",
            "role": "[[YOUR ROLE]]"
        },
        code=code,
        course=course,
    )
    text = f'''
    {','.join(emails)}

    {email_subject}

    {email_body}
    '''

    text = re.sub(r'<\/?\w+>', '', text)

    try:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        for recipient in emails:
            mail.Recipients.Add(recipient).Type = 3
        mail.Subject = email_subject
        mail.HtmlBody = email_body
        mail.Display()
    except Exception:
        with open("email.txt", "w") as file:
            file.write(text)
        tk.messagebox.showerror(
            message="Error Generating Email. Text was written to 'email.txt' ")


def begin_course_sync(*, course, progress_bar, status_label):
    """Summary
    
    Args:
        course (TYPE): Description
        progress_bar (TYPE): Description
        status_label (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    payload = {
        'comment': 'Automatic sync from publishing app',
        'copy_settings': True,
        'publish_after_initial_sync': False

    }
    response = requests.post(
        f'{api_url}/courses/{course["id"]}'
        + '/blueprint_templates/default/migrations',
        headers=headers,
        data=payload)

    if not response.ok:
        print(response)
        print(response.content)
        return

    migration = response.json()
    progress_bar.configure(mode='indeterminate')
    while response.ok \
        and migration['workflow_state'] in [
            'queued',
            'exporting',
            'imports_queued',
            'running']:
        print(response)
        print(migration)

        print(migration['workflow_state'])
        status_label.configure(text=f"migration['workflow_state']...")
        time.sleep(5)
        response = requests.get(
            f'{api_url}/courses/{course["id"]}'
            + '/blueprint_templates/default/'
            + f'migrations/{migration["id"]}',
            headers=headers)
        if response.ok:
            migration = response.json()

    print(response)
    print(response.content)


def publish_courses(*, courses: list):
    """Summary
    Publishes a set of courses.

    Args:
        courses (list): A list of course dicts
    """
    url = f'{api_url}/accounts/{ACCOUNT_ID}/courses'
    response = requests.put(url, headers=headers, data={
        'event': 'offer',

        # list of course ids
        'course_ids[]': map(lambda a: a['id'], courses)

    })
    if not response.ok:
        print(response)
        print(response.content)


def lock_module_items(course: dict):
    """Summary
    
    Args:
        course (dict): The course to lock items on
    """
    course_id = course['id']
    modules = get_modules(course_id)
    for module in modules:
        for item in module['items']:
            url = f"{api_url}/courses/{course_id}/" \
                + "blueprint_templates/default/restrict_item"
            id_ = ""
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
                if response.ok and response.status_code == 200:
                    id_ = response.json()["page_id"]
            elif type_ == "File":
                type_ = "file"
                id_ = item["content_id"]
            else:
                continue

            response = requests.put(url, headers=headers, data={
                "content_type": type_,
                "content_id": id_,
                "restricted": True,
            })
            if response.ok:
                print(response.json())
            else:
                print(response)
                print(response.text)
                print(json.dumps(item, indent=2))


def get_source_course_id(course_id):
    """Summary
    
    Args:
        course_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    migrations = requests.get(
        f'{api_url}/courses/{course_id}/content_migrations', headers=headers).json()
    print(migrations)
    # if there are no migrations return false
    if len(migrations) < 1:
        return False

    # sort by id descending so the first element is the latest created
    migrations.sort(reverse=True, key=lambda migration: migration['id'])
    return migrations[0]['settings']['source_course_id']


def remove_lm_annotations_from_course(course):
    """Summary
    
    Args:
        course (TYPE): Description
    """
    course_id = course['id']
    modules = get_modules(course_id)
    for module in modules:
        # find an item in the module called "Week ? Learning Materials"
        lm_page = next((filter(lambda item: item['type'] == 'Page' and re.search(
            r'Week \d+ Learning Materials', item['title']), module['items'])), None)
        if lm_page:
            full_page = requests.get(lm_page['url'], headers=headers).json()

            body = remove_lm_annnotations(full_page['body'])
            #print(json.dumps(full_page, indent=2))
            print(lm_page['url'])
            data = {
                'wiki_page[body]': body
            }
            print(data)
            response = requests.put(lm_page['url'], headers=headers,
                                    data=data)

            print(response.text)


syllabus_replacements = [{
    'find': r'<p>The instructor will conduct [^.]*\(48 hours during weekends\)\.',
    'replace': '<p>The instructor will conduct all correspondence with students related to the class in Canvas, and you should expect to receive a response to emails within 24 hours.'
}]


def update_syllabus_text(text):
    """Summary
    
    Args:
        text (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    for replacement in syllabus_replacements:
        text = re.sub(replacement['find'], replacement['replace'], text)
    return text


def update_syllabus(course_id):
    """Summary
    
    Args:
        course_id (TYPE): Description
    """
    url = f"{api_url}/courses/{course_id}?include[]=syllabus_body"
    response = requests.get(url, headers=headers)
    content = response.json()
    syllabus = update_syllabus_text(content["syllabus_body"])
    response = requests.put(f'{api_url}/courses/{course_id}',
                            headers=headers,
                            data={
                                "course[syllabus_body]": syllabus
                            }
                            )


def remove_lm_annnotations(text):
    """Summary
    
    Args:
        text (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    # one liners to replace
    replacements = [
        {
            'find': r'<p>\[Text for optional primary media element to be written by SME\]</p>',
            'replace': '',
        },

        {
            'find': r'\[[iI]nsert annotation for media\]',
            'replace': '',
        },
        {
            'find': r'<h3>\[Title for <span style="text-decoration: underline;">optional </span>secondary media element\]</h3>',
            'replace': '',
        },
        {
            'find': r'<h3><strong>\[Title for \w+ category of LMs\]</strong></h3>',
            'replace': 'Materials',
        },




    ]

    for replace in replacements:
        find = re.compile(replace['find'], flags=re.MULTILINE)
        print(replace['find'])
        text = re.sub('\\n', '\n', text)
        text = re.sub(r'(\s)\s+', '\1', text)
        match = re.findall(find, text.format())
        if match:
            print("FOUND", match)
            text = re.sub(find, replace['replace'], text)

    # remove these sections
    soup = BeautifulSoup(text, 'lxml')
    bq = soup.find('blockquote')
    if bq and "SME" in bq.text:
        parent = single_filter(lambda item: item.has_attr(
            'class') and 'cbt-content' in item['class'], bq.parents)
        print(parent)
        parent.decompose()

    divs = soup.find_all('div')
    div = single_filter(lambda item: item.has_attr(
        'class') and 'cbt-content' in item['class'] and '[LM Narrative' in item.text, divs)
    if div:
        div.decompose()

    out = str(soup.find('body'))
    out = re.sub(r'</?body>', '', out)
    return out


def single_filter(func, set, default=None):
    """Summary
    
    Args:
        func (TYPE): Description
        set (TYPE): Description
        default (None, optional): Description
    
    Returns:
        TYPE: Description
    """
    return next(filter(func, set), None)


def get_modules(course_id):
    """Summary
    
    Args:
        course_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f"{api_url}/courses/{course_id}/modules?include[]=items&include[]=content_details"
    print(url)
    return get_paged_data(url)


def update_progress_bar(progress_bar, value, maximum=100):
    """Summary
    
    Args:
        progress_bar (TYPE): Description
        value (TYPE): Description
        maximum (int, optional): Description
    """
    # update loading UI value after processing
    ui_root.update_idletasks()
    ui_root.update()
    progress_bar["value"] = (value / maximum) * 100
    ui_root.update_idletasks()
    ui_root.update()


browser_button = False
email_button = False


def replace_faculty_profiles(bp_course, courses, ui_root, progress_bar):
    """Summary
    
    Args:
        bp_course (TYPE): Description
        courses (TYPE): Description
        ui_root (TYPE): Description
        progress_bar (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    global browser_button
    global email_button
    # if the course has no associations, JUST queue up to update the input course
    ui_root = progress_bar.winfo_toplevel()
    if not courses:
        if tk.messagebox.askyesno(message=f"Course {bp_course['name']} does not have associated courses. Do you want to just get the bio for this course?"):
            courses = [bp_course]
        else:
            exit()

    pages = get_faculty_pages()
    profiles = []
    home_page_urls = []
    i = 1
    for course in courses:

        profile = get_course_profile(course, pages)
        profiles.append(profile)

        # overwrite_home_page returns the course url. add that to list.
        home_page_urls.append(overwrite_home_page(profile, course))

        # update loading UI value after processing
        ui_root.update_idletasks()
        ui_root.update()
        progress_bar["value"] = (i / len(courses)) * 100
        ui_root.update_idletasks()
        ui_root.update()
        i = i + 1

    bio_count = 0
    error_text = ""
    emails = []
    for profile in profiles:
        if not profile:
            error_text = error_text + "A course does not have a user associated"
            continue
        if len(profile["bio"]) < 5:
            error_text = error_text + \
                f'{profile["user"]["name"]} does NOT have a bio we can find\n'
        else:
            bio_count = bio_count + 1
            if "email" in profile["user"]:
                emails.append(profile["user"]["email"])
            else:
                error_text = error_text + \
                    ("\nNo Email Found for " + profile["user"]["name"])
    dialog_text = f"Finished, {bio_count} records updated successfully\n{error_text}"

    # this button opens a browser window for each updated course

    def open_browser_func():
        """Summary
        """
        for url in home_page_urls:
            webbrowser.open(url, new=2, autoraise=False)

    if browser_button:
        browser_button.configure(command=open_broswer_func)
    else:
        browser_button = tk.Button(
            master=ui_root, text="Open Courses", command=open_browser_func)
        browser_button.pack()

    if email_button:
        email_button.configure(command=lambda: generate_email(
            course=bp_course, courses=courses, constants=constants, emails=emails))
    else:
        email_button = tk.Button(master=ui_root, text="Try Email", command=lambda: generate_email(
            course=bp_course, courses=courses, constants=constants, emails=emails))
        email_button.pack()

    tk.messagebox.showinfo("force_import", dialog_text)

    return profiles


def save_bios(bios, path="bios.json"):
    """Summary
    
    Args:
        bios (TYPE): Description
        path (str, optional): Description
    """
    with open(path, 'w') as f:
        json.dump(bios, f, indent=2)


def get_faculty_pages(force=False):
    """Summary
    
    Args:
        force (bool, optional): Description
    
    Returns:
        TYPE: Description
    """
    print(force)
    if os.path.isfile("bios.json") and not force:
        with open("bios.json", 'r') as f:
            pages = json.load(f)
            print(len(pages))
    else:
        pages = get_paged_data(
            f"{live_url}/courses/{profile_pages_course_id}/pages?per_page=50&include=body", live_headers)
        save_bios(pages)
    return pages


def get_course(course_id):
    """Summary
    
    Args:
        course_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f'{api_url}/courses/{course_id}?include[]=term&include[]=grading_periods'
    response = requests.get(url, headers=headers)
    print(response)
    return response.json()


def format_profile_page(profile, course, homepage):
    """Summary
    
    Args:
        profile (TYPE): Description
        course (TYPE): Description
        homepage (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    text = ""
    # if it's cbt theme, run the new formatter
    if "cbt-banner-header" in homepage['body']:
        text = format_profile_page_newdev(profile, course, homepage)
    else:
        with open("template.html", 'r') as f:
            template = f.read()
        text = template.format(
            course_title=homepage[
                "title"] if "title" in homepage else f' Welcome to {course["name"]}',
            instructor_name=profile["display_name"] if "display_name" in profile else profile["user"]["name"],
            img_src=profile["img_src"],
            bio=profile["bio"])

    text = clean_up_bio(text)
    with open(f'profiles/{profile["user"]["id"]}_{course["id"]}.htm', 'wb') as f:
        f.write(text.encode("utf-8", "replace"))

    return text


def clean_up_bio(html):
    """Summary
    
    Args:
        html (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    html = re.sub(r'<p>\w*(&nbsp;)?\w*</p>', '', html)
    return html


def format_profile_page_newdev(profile, course, homepage):
    """Summary
    
    Args:
        profile (TYPE): Description
        course (TYPE): Description
        homepage (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    body = homepage['body']
    instructor_name = profile["display_name"] if "display_name" in profile else profile["user"]["name"]
    bio_body = profile["bio"]
    # change to api instead of site url
    data_url = re.sub('.com/', '.com/ap1/v1/', profile['img_src'])
    body = re.sub(
        r'<p>\w*<span>\w*Instructor bio coming soon!\w*</span>\w*</p>', bio_body, body)
    # replace image
    find_profile_image = re.compile(
        r'src="[^"]*"([^>]*)alt="male-profile-image-placeholder.png" data-api-endpoint="[^"]*"')
    homepage = re.sub(
        find_profile_image, f'src="{profile["img_src"]}"\1data-api-endpoint="{data_url}"', body)

    return homepage


def get_course_profile(course, pages):
    """Summary
    
    Args:
        course (TYPE): Description
        pages (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    return get_course_profile_from_pages(course, pages)


def get_course_profile_from_pages(course, pages):
    """Summary
    
    Args:
        course (TYPE): Description
        pages (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    instructor = get_canvas_instructor(course["id"])

    prompt = f'No instructor found for {course["name"]} do you want to to search for an instructor by name?'
    if not instructor:
        while tk.messagebox.askyesno(message=prompt):
            name = tk.simpledialog.askstring(
                title="Name", prompt="Please enter the full user name of the person you would like to find")
            users = []
            result = requests.get(
                f"{api_url}/accounts/self/users?search_term={name}", headers=headers)
            if result.ok and len(result.json()) > 0:
                for user in result.json():
                    if tk.messagebox.askyesno(message=f"Do you want to use {user['name']}?"):
                        instructor = user
                        break
                if instructor:
                    break
            else:
                print(result)
                print(result.json())
                prompt = f"No results found for {name}. Do you want to search for another instructor?"
        if not instructor:
            return None
    course_id = course["id"]
    profile = get_instructor_profile_from_pages(instructor, pages)

    if not profile or len(profile["bio"]) == 0:
        profile = get_instructor_profile_submission(instructor)
    return profile


def get_course_profile_from_assignment(course):
    """Summary
    
    Args:
        course (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    instructor = get_canvas_instructor(course["id"])
    course_id = course["id"]
    if instructor is not None:
        print("The instructor of the course {} is {}".format(course_id, instructor))
    else:
        print("The instructor of the course {} cannot be found.".format(course_id))
    return get_instructor_profile_submission(instructor)


def get_blueprint_courses(bp_id):
    """Summary
    
    Args:
        bp_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f"{api_url}/courses/{bp_id}/blueprint_templates/default/associated_courses?per_page=50"
    response = requests.get(url, headers=headers)
    courses = response.json()

    if "errors" in courses:
        print(courses["errors"])
        return False

    next_page_link = "!"
    while len(next_page_link) != 0 and "link" in response.headers:
        pagination_links = response.headers["Link"].split(",")
        for link in pagination_links:
            if 'next' in link:
                next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
                response = requests.get(next_page_link, headers=headers)
                courses = courses + response.json()
                print("added courses at", next_page_link)
                break
            else:
                next_page_link = ""
            print(link)

    return courses


def overwrite_home_page(profile, course):
    """Summary
    
    Args:
        profile (TYPE): Description
        course (TYPE): Description
    
    Returns:
        TYPE: Description
    
    Raises:
        ValueError: Description
    """
    # Make a GET request to the Canvas LMS API to get the homepage of the course.
    url = f'{api_url}/courses/{course["id"]}/front_page'
    page_url = f'{html_url}/courses/{course["id"]}/'
    print(page_url)
    response = requests.get(url, headers=headers)

    # Check the response status code.
    if response.status_code != 200:
        raise ValueError(
            'Failed to get homepage of course: {}'.format(response.status_code))

    # Parse the homepage HTML content.

    homepage_html = response.json()['body']
    homepage = {"course_title": None, "body": homepage_html}
    soup = BeautifulSoup(homepage_html, 'html.parser')
    h2Tags = soup.find_all('h2')
    if len(h2Tags) > 0:
        homepage["title"] = h2Tags[0].text

    if profile:
        data = {'wiki_page[body]': format_profile_page(
            profile, course, homepage)}

        response = requests.put(url, headers=headers, data=data)
        print(response)
    else:
        print("instructor not found for this course; skipping")

    return page_url


def get_instructor_profile_from_pages(user, pages):
    """Summary
    
    Args:
        user (TYPE): Description
        pages (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    first_name = user["name"].split(" ")[0]
    last_name = user["name"].split(" ")[-1]

    def restrictive_filter_func(entry):
        """Summary
        
        Args:
            entry (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        return user["name"].lower() in entry["title"].lower()

    def premissive_filter_func(entry):
        """Summary
        
        Args:
            entry (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        return last_name.lower() in entry["title"].lower() and first_name.lower() in entry["title"].lower()

    def extremely_permissive_filter_func(entry):
        """Summary
        
        Args:
            entry (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        return last_name.lower() in entry["title"].lower() or first_name.lower() in entry["title"].lower()

    prompt_user = False
    potentials = list(filter(restrictive_filter_func, pages))
    if len(potentials) == 0:
        potentials = list(filter(premissive_filter_func, pages))

    if len(potentials) == 0:
        # Prompt the user to check this/these names because we've used the extremely permissive function
        prompt_user = True
        potentials = list(filter(extremely_permissive_filter_func, pages))

    out = dict(user=user, bio="", img="", img_src="")
    page = None

    if len(potentials) > 1 or prompt_user:
        print(json.dumps(user, indent=2))
        print("_________________POTENTIALS______________________")
        print(json.dumps(potentials, indent=2))
        print("----------------------------------------------------")

        for potential in potentials:
            if not "body" in potential:
                continue
            if tk.messagebox.askyesno(message=f"No direct match found for {user['name']}. Do you want to use { potential['title'] }?"):
                page = potential
    else:
        page = potentials[0]

    if not page:
        tk.messagebox.showinfo(
            message=f"No profile found matching {user['name']}")
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

    # get display name just in case
    out["display_name"] = False
    for p in soup.find_all('p'):
        previous_p = p.find_previous_sibling('p')
        if "instructor" in p.text.lower() and previous_p is not None:
            print(previous_p.text)
            out["display_name"] = previous_p.text

    # get image output
    imgs = soup.find_all("img")
    for img in imgs:
        out["img_src"] = img["src"]

    return out


def get_instructor_profile_submission(user):
    """Summary
    
    Args:
        user (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f"{api_url}/courses/{instructor_course_id}/assignments/{profile_assignment_id}/submissions/{user['id']}"
    response = requests.get(url, headers=headers)
    submission = response.json()
    print(submission)
    bio = submission["body"] if (
        "body" in submission and submission["body"] is not None) else ""
    pic_path = ""
    if "attachments" in submission:
        for attachment in submission["attachments"]:
            url = attachment["url"]
            attachmentData = requests.get(url, headers=headers)

            filename = attachment["filename"]
            with open(filename, 'wb') as f:
                f.write(attachmentData.content)
            filename = attachment["filename"]

            # handle doc
            if os.path.splitext(filename)[1] == ".docx" or os.path.splitext(filename)[1] == ".zip":
                doc = docx.Document(filename)
                with open(filename, 'rb') as f:
                    zip = zipfile.ZipFile(f)

                    for info in zip.infolist():
                        is_image = (
                            "jpg" in info.filename or "png" in info.filename or "jpeg" in info.filename)
                        if is_image:
                            pic_path = zip.extract(
                                info, f"/{user['name']}{user['id']}profile{os.path.splitext(info.filename)[1]}")

                for para in doc.paragraphs:
                    if len(para.text) > 10:
                        bio = bio + (f"<p>{para.text}</p>\n")

            # if it's an attached image
            elif os.path.splitext(filename)[1] in ['.jpg', '.jpeg', '.png']:
                with open(f"{user['name']}{user['id']}profile{os.path.splitext(filename)[1]}", "wb") as f:
                    f.write(attachmentData.content)
                    pic_path = os.path.realpath(f.name)

        # todo: upload resized profile pic and populate upload_url
    img_upload_url = ""
    if len(pic_path) > 0:
        pic_path = resize_image(pic_path, max_profile_image_size)
        img_upload_url = upload_image(pic_path, instructor_course_id)

    img_src = img_upload_url if len(
        img_upload_url) > 0 else default_profile_url

    return dict(user=user, bio=bio, img_src=img_src, local_image_path=pic_path)

# TODO write this in


def resize_image(path, max_width):
    """Summary
    
    Args:
        path (TYPE): Description
        max_width (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    input_path = path
    output_path = path
    with Image.open(input_path) as img:
        print(img.size)
        if max_width >= img.size[0]:
            print(max_width, img.size)
            return input_path

        target_width = max_width

        # Calculate the new height to preserve the aspect ratio
        width_percent = (target_width / float(img.size[0]))
        new_height = int((float(img.size[1]) * float(width_percent)))

        # Resize the image using the appropriate resampling filter
        resized_img = img.resize(
            (target_width, new_height), Image.Resampling.BILINEAR)

        # Save the resized image
        resized_img.save(output_path)
        print(output_path)
    return output_path

# TODO: write this in


def upload_image(pic_path, course_id):
    """Summary
    
    Args:
        pic_path (TYPE): Description
        course_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    return ""


def get_instructor_page(user):
    """Summary
    
    Args:
        user (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f"{api_url}/courses/{profile_pages_course_id}/pages?per_page=999&search={urllib.parse.quote(user['name'])}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    pages = response.json()

    pagination_links = response.headers["Link"].split(",")
    next_page_link = pagination_links[1].split(";")[0].split("<")[
        1].split(">")[0]
    firstTime = True
    while len(pagination_links) > 4 or firstTime:
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
            next_page_link = pagination_links[1].split(";")[0].split("<")[
                1].split(">")[0]
            print(next_page_link)

    for page in pages:
        print(page["title"])


def get_canvas_course_home_page(course_id):
    """Summary
    
    Args:
        course_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    # Make the request to the Canvas LMS course home page.
    url = f"https://unity.instructure.com/courses/{course_id}"
    response = requests.get(url, headers=headers)
    return response.content


def get_canvas_instructor(course_id):
    """Summary
    
    Args:
        course_id (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f"{api_url}/courses/{course_id}/users?" + \
        "enrollment_type=teacher"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    users = response.json()
    for user in users:
        return user

    return None


def get_paged_data(url, headers=headers):
    """Summary
    
    Args:
        url (TYPE): Description
        headers (TYPE, optional): Description
    
    Returns:
        TYPE: Description
    """
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
