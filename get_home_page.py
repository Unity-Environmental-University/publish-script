"""Summary

Attributes:
    lm_replacements (TYPE): A list of {find, replace} dicts
        to re.sub to perform on learning materials
    syllabus_replacements (list): A list of {find, replace} dicts
        with paired regexes to run on syllabi of both the blueprint
        and the DEV_ course

Deleted Attributes:
    log_filename (str): A file to log logs to. Not currently used.
    log_string (str): The opening string of the log
    CONSTANTS_FILE (str): The path to the constants file
    url (TYPE): Description
    max_profile_image_size (int): The max width of profile images to scale
        downloaded profile images to
    api_token (str): A global variable holding the api access token
    api_url (str): A global variable holding the api url
    html_url (str): A base url for the site
    instructor_course_id (int): A link to the course ID for instructors
    profile_assignment_id (TYPE): The ID of the assignment
        where user profiles are kept
    profile_pages_course_id (TYPE): The course ID of
        the course with all the faculty pages
    ACCOUNT_ID (int): The main account ID of the
        unity account where student courses are places
    accounts (list): A list of all accounts
    default_profile_url (str): A url to the default profile image
    headers (dict): a global variable holding the header used in requests
    live_headers (dict): headers for the live site.
        Only used to read relevant data when testing
    live_url (str): A url to the live site even when testing
    ROOT_ACCOUNT_ID (TYPE): The account ID for the rootmost unity Account
    account_ids (dict): A dictionary of account ids by account name
    browser_button (bool): A button that opens several browser windows
    email_button (bool): A button that tries to email professors
        associated with courses
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
from tkinter import messagebox
from PIL import Image


syllabus_replacements = [{
    'find': r'<p>The instructor will conduct [^.]*'
    r'\(48 hours during weekends\)\.',

    'replace': '<p>The instructor will conduct all correspondence with '
    r'students related to the class in Canvas, and you should expect to '
    r'receive a response to emails within 24 hours.'
}]

lm_replacements = [
    {
        'find': r'<p>\[Text for optional primary'
        r'media element to be written by SME\]</p>',

        'replace': '',
    },

    {
        'find': r'\[[iI]nsert annotation for media\]',
        'replace': '',
    },
    {
        'find':
            r'<h3>\[Title for <span style="text-decoration: underline;">'
            r'optional </span>secondary media element\]</h3>',
        'replace': '',
    },
    {
        'find':
            r'<h3><strong>\[Title for \w+ category of LMs\]</strong></h3>',
        'replace': 'Materials',
    },
]

CONSTANTS_FILE: str = 'constants.json'
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

default_profile_url: str = f"{html_url}/users/9230846/files/156109264/preview"
live_url: str = constants["liveUrl"]

# Authorize the request.
headers: dict = {"Authorization": f"Bearer {api_token}"}
live_headers: dict = {"Authorization": f'Bearer {constants["liveApiToken"]}'}


accounts: list = requests.get(f'{api_url}/accounts', headers=headers).json()
account_ids: dict = dict()
for account in accounts:
    account_ids[account['name']] = account['id']

ACCOUNT_ID: int = account_ids['Distance Education']
ROOT_ACCOUNT_ID: int = account_ids['Unity College']


def main():
    """Summary
        Main loop. Opens an interface you can perform various
        course publishing operations with.
    """

    window = tk.Tk()
    window.geometry("600x400")
    initial_value: str = ""
    if len(sys.argv) > 1:
        initial_value = sys.argv[1]
    else:
        try:
            initial_value = get_course_id_from_string(window.clipboard_get())
        except tk.TclError:
            print("Clipboard empty")

    label = tk.Label(window, text="Enter the course name")
    label.pack()

    course_string_var: object = tk.StringVar(
        master=window,
        value=initial_value)

    text_entry = tk.Entry(
        window,
        textvariable=course_string_var)
    text_entry.pack()

    enter_binding_id = None

    def callback(event=None):
        success = course_entry_callback(
            window=window,
            status_label=label,
            to_remove=[button, text_entry],
            course_string=course_string_var.get())
        if success:
            window.unbind('<Return>', enter_binding_id)

    window.bind('<Return>', callback)

    button = tk.Button(
        master=window,
        text="Get Course",
        command=callback)
    button.pack()

    window.mainloop()


def course_entry_callback(
        *,
        to_remove: list,
        course_string: str,
        window: object,
        status_label: tk.Label):
    """Summary
        Callback to search for the course.
    Args:
        to_remove (list): A list of widgets to destroy on execution
        course_string (str): the string of the course to use
        window (object): the window we're working in
        status_label (tk.Label): Place to display
    """
    course_id = get_course_id_from_string(course_string)
    course = get_course(course_id)
    if not course_id:
        status_label.configure(text="Course Not Found")
        return False
    else:
        status_label.configure(text=f"Course Found\n{course['name']}")
        setup_main_ui(
            bp_course=get_course(course_id),
            window=window,
            status_label=status_label)
        for widget in to_remove:
            widget.destroy()
        return True


def setup_main_ui(
        *,
        bp_course,
        window,
        status_label):
    """Summary
        Sets up the main workflow UI

    Args:
        bp_course (TYPE): the course we're working with
        window (TYPE): The widow to create UI in
        status_label (TYPE): Description
    """
    bp_id = bp_course['id']
    print(bp_course)
    # source_course_id = get_source_course_id(bp_id)
    courses = get_blueprint_courses(bp_id)

    # Create a progress bar
    progress_bar = ttk.Progressbar(
        window,
        orient="horizontal",
        length=200,
        mode="determinate")
    progress_bar.pack()

    updates = [
        {
            'name': 'update_syllabus',
            'argument': 'syllabus',
            'message': "Do you want to update syllabus language"
            " in this and any source?"
            "\nDo this before sync!",
            'func': lambda: [
                update_syllabus(bp_id),
                update_syllabus(get_source_course_id(bp_id))]
        },
        {
            'name': 'remove_lm_annnotations',
            'argument': 'lm',
            'message': "Do you want to remove "
            f"lm annotations from\n{bp_course['name']}?",
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
            ' redownload the latest faculty profiles?',
            'func': lambda: get_faculty_pages(force=True)
        },
        {
            'name': 'sync',
            'message': 'Do you want sync associated courses?'
            '\nThis could take a sec.',
            'error': 'There was a problem syncing\n{e}',
            'func': lambda: begin_course_sync(
                course=bp_course,
                progress_bar=progress_bar,
                status_label=status_label),
        },

        {
            'name': 'profiles',
            'argument': 'profiles',
            'message': 'Do you want to update profiles in associated courses?',
            'error': 'There was a problem updating profile pages\n{e}',
            'func': lambda: replace_faculty_profiles(
                bp_course=bp_course,
                courses=courses,
                window=window,
                progress_bar=progress_bar),
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
        opening_dialog(
            course=bp_course,
            updates=updates,
            window=window,
            status_label=status_label)


def opening_dialog(*,
                   window: object,
                   course: dict,
                   updates: list,
                   status_label: object):
    """Summary
        Starts the process of creating an opening dialog window for the
        application
    
    Args:
        window (object): The base program window to render into
        course (dict): The blueprint course we are working with
        updates (list): The Upda
        status_label (object): Description
    """
    checkboxes = []
    for update in updates:
        boolVar = tk.BooleanVar()
        button = tk.Checkbutton(
            window,
            text=update['message'],
            onvalue=True,
            offvalue=False,
            variable=boolVar)
        checkboxes.append(button)
        update['run'] = boolVar
        button.pack()

    def callback(event=None):
        handle_run(
            updates,
            status_label)

    window.bind('<Return>', callback)

    button = tk.Button(
        master=window,
        text="Run",
        command=callback)
    button.pack()


def handle_run(updates: list, status_label: object):
    """Summary
        Callback for when the user clicks 'run' on the opening dialog
        Iterates across the workflow options to check which are true
        and executes them in order.

    Args:
        updates (list): A list of dicts containing the callbacks
         and data for each checkbox / workflow step on the interface
        status_label (object): A label widget to update with status info
    """
    window = status_label.winfo_toplevel()
    for update in updates:
        try:
            print(update['name'], update['run'].get())
            if update['run'].get():
                status_label.config(text=f"Running {update['name']}")
                window.update()
                print(update)
                update['func']()
        except Exception as e:
            messagebox.showerror(message=update['error'].format(
                e=str(e)) + "\n" + traceback.format_exc())
            print(traceback.format_exc())

    status_label.config(text=f'Finished!')


def generate_email(
        *,
        course: dict,
        courses: list,
        emails: list,
        window: object):
    """Summary
        Generates an an email to a list of recipients and attempts to open
        outlook. On failure, copies to clipboard.

    Args:
        course (dict): The BP_ course we're operating on
        courses (list): A list of all the courses we've operated on
        emails (list): A list of all the emails to bcc
        window (object): Description
        I may change this to example_course_data
    """
    with open("email_template.html", 'r') as f:
        template = f.read()

    code = course["course_code"][3:]

    example_course_data = get_course(
        courses[0]['id'] if courses
        else course['id'])
    print(json.dumps(example_course_data, indent=2))

    start_date = datetime.datetime.fromisoformat(
        example_course_data['term']["start_at"])
    start_date = start_date + datetime.timedelta(days=7)

    email_subject =\
        f'{course["course_code"][3:]} Section(s) Ready Notification'

    email_body = template.format(
        term={
            "name": example_course_data['term']['name'],
            "start": start_date.strftime('%B %#d')
        },
        creator={
            "name": "[[YOUR NAME]]",
            "role": "[[YOUR ROLE]]"
        },
        code=code,
        course=course,
    )

    try:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        for recipient in emails:
            mail.Recipients.Add(recipient).Type = 3
        mail.Subject = email_subject
        mail.HtmlBody = email_body
        mail.Display()

    except Exception:
        email_body = f"<p>bcc:{', '.join(emails)}</p>\n{email_body}"
        with open("email.htm", "w") as file:
            file.write(email_body)

        tk.messagebox.showerror(
            message="Error Generating Email."
            "Text has been copied to an html file which will open now.")

        webbrowser.open(
            f"file://{os.path.abspath('email.htm')}",
            new=1,
            autoraise=True)


def begin_course_sync(
        *,
        course: dict,
        progress_bar: object,
        status_label: object) -> dict:
    """Summary
        Begins the sync process of the blueprint to its member course
    
    Args:
        course (dict): The blueprint course
        progress_bar (object): The progress bar to update. Not sure if we
        status_label (object): The status label to update with info
        have enough info to use this though
    
    Returns:
        dict: The migration data dict if the operation was a success,
        otherwise False
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
        return False

    # poll the migration object until it is done
    migration = response.json()
    while response.ok \
        and migration['workflow_state'] in [
            'queued',
            'exporting',
            'imports_queued',
            'running']:
        print(response)
        print(migration)

        print(migration['workflow_state'])
        status_label.configure(text=f"{migration['workflow_state']}...")
        time.sleep(2)
        response = requests.get(
            f'{api_url}/courses/{course["id"]}'
            + '/blueprint_templates/default/'
            + f'migrations/{migration["id"]}',
            headers=headers)
        if response.ok:
            migration = response.json()

    print(response)
    print(response.content)
    return migration


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
        Locks all module items in a blueprint course
    
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


def get_source_course_id(course_id: int) -> int:
    """Summary
        Gets the id of the first course that migrated data into this one
    
    Args:
        course_id (int): The id of the course to check
    
    Returns:
        int: The course id of the source course
    """
    migrations = requests.get(
        f'{api_url}/courses/{course_id}/content_migrations',
        headers=headers).json()
    print(migrations)
    # if there are no migrations return false
    if len(migrations) < 1:
        return False

    # sort by id descending so the first element is the latest created
    migrations.sort(reverse=True, key=lambda migration: migration['id'])
    return migrations[0]['settings']['source_course_id']


def remove_lm_annotations_from_course(course):
    """Summary
        Removes placeholder text for annotators from a course'
        learning materials
    
    Args:
        object (TYPE): Description
    
    Deleted Parameters:
        course (TYPE): The course to operate on
    """
    course_id = course['id']
    modules = get_modules(course_id)
    for module in modules:
        # find an item in the module called "Week ? Learning Materials"
        lm_page = next((filter(
            lambda item: item['type'] == 'Page' and re.search(
                r'Week \d+ Learning Materials', item['title']),
            module['items'])), None)
        if lm_page:
            full_page = requests.get(lm_page['url'], headers=headers).json()

            body = remove_lm_annnotations(full_page['body'])
            print(lm_page['url'])
            data = {
                'wiki_page[body]': body
            }
            print(data)
            response = requests.put(lm_page['url'], headers=headers,
                                    data=data)

            print(response.text)


def update_syllabus_text(text: str):
    """Summary
        Executes a series of find/replaces on the text of a syllabus
    
    Args:
        text (str): The syllabus body html
    
    Returns:
        TYPE: The syllabus with all operations performed
    """

    global syllabus_replacements
    for replacement in syllabus_replacements:
        text = re.sub(replacement['find'], replacement['replace'], text)
    return text

def update_syllabus(course_id: int):
    """Summary
        Updates the syllabus of a specific course id
    
    Args:
        course_id (int): The id of the course to operate on
    """
    url = f"{api_url}/courses/{course_id}?include[]=syllabus_body"
    response = requests.get(url, headers=headers)
    content = response.json()
    if not response.ok:
        return False
    print(content)
    syllabus = update_syllabus_text(content["syllabus_body"])
    response = requests.put(
        f'{api_url}/courses/{course_id}',
        headers=headers,
        data={
            "course[syllabus_body]": syllabus})


def remove_lm_annnotations(text: str) -> str:
    """Summary
        Runs a list of regex replacements on html text of a
        Learning Material page (replacements, defined above)
    
    Args:
        text (str): An html string containing
        the body of a learning materials page
    
    Returns:
        str: An html string with the regexs run on it
    """
    # one liners to replace
    global lm_replacements

    for replace in lm_replacements:
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
        parent = single_filter(
            lambda item: item.has_attr('class')
            and 'cbt-content' in item['class'],
            bq.parents)
        print(parent)
        parent.decompose()

    divs = soup.find_all('div')
    div = single_filter(lambda item: item.has_attr(
        'class') and 'cbt-content' in item['class']
        and '[LM Narrative' in item.text, divs)
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


def get_modules(course_id: int) -> list:
    """Gets all modules including module item details
    
    Args:
        course_id (int): The ID of the course
    
    Returns:
        list: A list of module dicts
    """
    url: str = f"{api_url}/courses/{course_id}/modules?" \
        + "include[]=items&include[]=content_details"
    print(url)
    return get_paged_data(url)


def update_progress_bar(
        progress_bar: object,
        value: float,
        maximum: float = 100.0):
    """Summary
        Updates the progress of a progress bar object.
        Defaults to out of 100
        Sets progress to max / value
    
    Args:
        progress_bar (object): the progress bar to update
        value (float): the current value the bar is currently at
        maximum (float, optional): the max value the bar is at
    """
    # update loading UI value after processing
    ui_root = progress_bar.winfo_toplevel()
    ui_root.update_idletasks()
    ui_root.update()
    progress_bar["value"] = (value / maximum) * 100
    ui_root.update_idletasks()
    ui_root.update()


browser_button: object = False
email_button: object = False


def replace_faculty_profiles(
        *,
        bp_course: dict,
        courses: list,
        window: object,
        progress_bar: object) -> list:
    """Summary
        Iterates across courses, grabs the instrutor profile pages and updates
        the home page with bio and pic info.
    
    Args:
        bp_course (dict): The blueprint course governing the courses
        courses (list): A list of courses to update
        ui_root (object): The root ui window. We can probably get rid of this
        progress_bar (object): The progress bar to update
        at some point as we can access it through progress_bar
        we're editing OR, if not a blueprint, the single course we're
        updating the home page of
    
    Returns:
        list: A list of faculty profile objects
    """
    global browser_button
    global email_button
    # if the course has no associations,
    # JUST queue up to update the input course
    if not courses:
        if tk.messagebox.askyesno(
                message=f"Course {bp_course['name']}"
                "does not have associated courses."
                "Do you want to just get the bio for this course?"):

            courses = [bp_course]
        else:
            return

    pages = get_faculty_pages()
    profiles = []
    home_page_urls = []
    i = 1
    for course in courses:
        print(json.dumps(course))
        profile = get_course_profile(course, pages)
        profiles.append(profile)

        # overwrite_home_page returns the course url. add that to list.
        home_page_urls.append(overwrite_home_page(profile, course))

        # update loading UI value after processing
        window.update_idletasks()
        window.update()
        progress_bar["value"] = (i / len(courses)) * 100
        window.update_idletasks()
        window.update()
        i = i + 1

    bio_count = 0
    error_text = ""
    emails = []
    for profile in profiles:
        if not profile:
            error_text = error_text
            "A course does not have a user associated"
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

    dialog_text = f"Finished, {bio_count} " \
        + f" records updated successfully\n{error_text}"

    # this button opens a browser window for each updated course
    if browser_button:
        browser_button.configure(
            command=lambda: open_browser_func(home_page_urls))

    else:
        browser_button = tk.Button(
            master=window,
            text="Open Courses",
            command=lambda: open_browser_func(home_page_urls))

        browser_button.pack()

    def email_func():
        """Summary
        """
        generate_email(
            course=bp_course,
            courses=courses,
            window=window,
            emails=emails)

    if email_button:
        email_button.configure(command=email_func)
    else:
        email_button = tk.Button(
            master=window,
            text="Try Email",
            command=email_func)
        email_button.pack()

    tk.messagebox.showinfo("force_import", dialog_text)

    return profiles


def open_browser_func(urls):
    """
    Args:
        urls (list): A list of urls
    """
    for url in urls:
        webbrowser.open(url, new=2, autoraise=False)


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
            f"{live_url}/courses/{profile_pages_course_id}"
            "/pages?per_page=50&include=body",
            live_headers)
        save_bios(pages)
    return pages


def get_course(course_id: int) -> dict:
    """Summary
        Gets a course by ID
    
    Args:
        course_id (int): Id of the course to get
    
    Returns:
        dict: A dictionary containing the json parsed course
    """
    url = f'{api_url}/courses/{course_id}' \
        + '?include[]=term&include[]=grading_periods'
    response = requests.get(url, headers=headers)
    print(url)
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
            course_title=homepage["title"] if "title" in homepage
            else f' Welcome to {course["name"]}',

            instructor_name=profile["display_name"] if
            "display_name" in profile
            else profile["user"]["name"],

            img_src=profile["img_src"],
            bio=profile["bio"])

    text = clean_up_bio(text)
    profile_path = f'profiles/{profile["user"]["id"]}_{course["id"]}.htm'
    with open(profile_path, 'wb') as f:
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
    bio_body = profile["bio"]
    # change to api instead of site url
    data_url = re.sub('.com/', '.com/ap1/v1/', profile['img_src'])
    body = re.sub(
        r'<p>\w*<span>\w*Instructor bio coming soon!\w*</span>\w*</p>',
        bio_body,
        body)
    # replace image
    find_profile_image = r'src="[^"]*"([^>]*)' \
        + 'alt="male-profile-image-placeholder.png"' \
        + r'data-api-endpoint="[^"]*"'
    homepage = re.sub(
        find_profile_image,
        f'src="{profile["img_src"]}"\1data-api-endpoint="{data_url}"',
        body)

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

    prompt = f'No instructor found for {course["name"]} ' \
        + 'do you want to to search for an instructor by name?'

    if not instructor:
        while tk.messagebox.askyesno(message=prompt):
            name = tk.simpledialog.askstring(
                title="Name",
                prompt="Please enter the full user name"
                "of the person you would like to find")

            result = requests.get(
                f"{api_url}/accounts/self/users?search_term={name}",
                headers=headers)
            if result.ok and len(result.json()) > 0:
                for user in result.json():
                    if tk.messagebox.askyesno(
                            message=f"Do you want to use {user['name']}?"):
                        instructor = user
                        break
                if instructor:
                    break
            else:
                print(result)
                print(result.json())
                prompt = f"No results found for {name}. " \
                    + "Do you want to search for another instructor?"
        if not instructor:
            return None

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
        print("The instructor of the course {} is {}".format(
            course_id,
            instructor))
    else:
        print("The instructor of the course {} cannot be found.".format(
            course_id))
    return get_instructor_profile_submission(instructor)


def get_blueprint_courses(bp_id):
    """Summary
        Gets a list of courses associated with a blueprint course id
    
    Args:
        bp_id (TYPE): The blueprint course ID
    
    Returns:
        TYPE: A list of courses associated with this blueprint
    """
    url = f"{api_url}/courses/{bp_id}/"\
        "blueprint_templates/default/associated_courses?per_page=50"
    courses = get_paged_data(url)

    return courses


def overwrite_home_page(profile: dict, course: dict) -> str:
    """Summary
        Replaces the picture and bio element, if able
        of a course home page
     Args:
        profile (dict): The faculty profile dictionary
        course (dict): The course dictionary
    
     Returns:
        TYPE: The url of the changed page
    
    Raises:
        Exception: Description
    
    Args:
        profile (dict): Description
        course (dict): Description
    
    Returns:
        str: Description
    
    No Longer Raises:
        ValueError: Couldn't access home page of course
    """

    url = f'{api_url}/courses/{course["id"]}/front_page'
    page_url = f'{html_url}/courses/{course["id"]}/'
    print(page_url)
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            'Failed to get homepage of course: {}'.format(
                response.status_code))

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

    # A list of filter functions to apply from least to most permissive
    filter_funcs: list = [
        lambda entry: user["name"].lower() in entry["title"].lower(),

        lambda entry: last_name.lower() in entry["title"].lower()
        and first_name.lower() in entry["title"].lower(),

        lambda entry: last_name.lower() in entry["title"].lower()
        or first_name.lower() in entry["title"].lower(),
    ]

    iterations = 0
    for func in filter_funcs:
        potentials = list(filter(func, pages))
        if len(potentials) > 0:
            break
        iterations = iterations + 1

    out = dict(user=user, bio="", img="", img_src="")
    page = None

    # if we are more than two filters deep,
    # or there are more than one potential user,
    # prompt the user to confirm

    if len(potentials) > 1 or iterations > 2:
        print(json.dumps(user, indent=2))
        print("_________________POTENTIALS______________________")
        print(json.dumps(potentials, indent=2))
        print("----------------------------------------------------")
        for potential in potentials:
            if "body" not in potential:
                continue
            if tk.messagebox.askyesno(
                message=f"No direct match found for {user['name']}."
                    f"Do you want to use { potential['title'] }?"):
                page = potential

    # alert the user if there are no results
    elif len(pages) == 0:
        tk.messagebox.showinfo(
            message=f"No profile found matching {user['name']}")
        return False

    # otherwise pick the first result
    else:
        page = potentials[0]

    # Now that we hage the page, grab the instructor info
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
    url = f"{api_url}/courses/{instructor_course_id}" \
        f"/assignments/{profile_assignment_id}/submissions/{user['id']}"
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
            if os.path.splitext(filename)[1] == ".docx" \
                    or os.path.splitext(filename)[1] == ".zip":
                doc = docx.Document(filename)
                with open(filename, 'rb') as f:
                    zip = zipfile.ZipFile(f)

                    for info in zip.infolist():
                        is_image = (
                            "jpg" in info.filename
                            or "png" in info.filename
                            or "jpeg" in info.filename)
                        if is_image:
                            pic_path = zip.extract(
                                info,
                                f"/{user['name']}{user['id']}"
                                f"profile{os.path.splitext(info.filename)[1]}")

                for para in doc.paragraphs:
                    if len(para.text) > 10:
                        bio = bio + (f"<p>{para.text}</p>\n")

            # if it's an attached image
            elif os.path.splitext(filename)[1] in ['.jpg', '.jpeg', '.png']:
                with open(
                        f"{user['name']}"
                        f"{user['id']}profile"
                        f"{os.path.splitext(filename)[1]}",
                        "wb") as f:
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


# TODO: Write this function
def upload_image(pic_path: str, course_id: int) -> str:
    """Summary
        NOT IMPLEMENTED
        Uploads a locally stored image to a course and returns the url
        path to that file
    
    Args:
        pic_path (str): The local 
        course_id (int): Description
    
    Returns:
        str: Description
    """
    return ""


def get_instructor_page(user):
    """Summary
    
    Args:
        user (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    url = f"{api_url}/courses/{profile_pages_course_id}/pages" \
        f"?per_page=999&search={urllib.parse.quote(user['name'])}"
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
            next_page_link = pagination_links[1].split(";")[0] \
                .split("<")[1].split(">")[0]
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


def get_paged_data(url: str, headers: dict = headers) -> list:
    """Summary
        returns a list of data from a get request, going through
        multiple pages of data requests as necessary
    
    Args:
        url (str): The url to query
        headers (dict, optional): Headers for the request
    
    Returns:
        list: Description
    """
    response = requests.get(url, headers=headers)
    out = response.json()
    if not response.ok:
        return None
    next_page_link = "!"
    while len(next_page_link) != 0 \
            and 'link' in response.headers \
            and response.ok:
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


def get_course_id_from_string(course_string: str) -> int:
    """Summary

    Args:
        course_string(str): The string to match
    Returns:
        int: the course id if it matches a regex for course id
    """
    id_match = re.search(r'(\d{7}\d*)', course_string)
    course_name_match = re.search(r'(\w+_\w{4}\d{3})', course_string)

    if id_match:
        print(id_match)
        return int(id_match.group(1))
    elif course_name_match:
        print(course_name_match)
        return get_course_by_code(course_name_match.group(1))
    else:
        return None


def get_course_by_code(code: str) -> dict:
    """Summary
        attempts to find a course by course code,
        inclusive of starting component
        currently does not support
        course sections
    
    Args:
        code (str): The course code
    
    Returns:
        dict: A dictionary representing the first course found
        or None if no match
    """
    url = f"{api_url}/accounts/{ROOT_ACCOUNT_ID}/courses"
    print(url)
    response = requests.get(
        url,
        headers=headers,
        params={"search_term": f"{code}"})
    print(response)
    print(response.json())
    if response.ok and len(response.json()) > 0:
        courses = response.json()
        return courses[0]['id']
    else:
        return None


main()
