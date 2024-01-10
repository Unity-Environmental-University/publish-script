import inspect
import warnings
from functools import cached_property

try:
    import aiohttp
except ImportError as e:
    aiohttp = None
    warnings.warn(e.msg)
    print("aiohttp not loaded, no async operations")

import asyncio
import datetime
import json
import os
import re
import sys
import time
import tkinter as tk
import traceback
import urllib.parse
import webbrowser
import zipfile
from tkinter import messagebox, StringVar, simpledialog
from tkinter import ttk
from typing import *
import docx
import requests
import win32com.client as win32
from PIL import Image
from bs4 import BeautifulSoup

API_TOKEN: str
API_URL: str
HTML_URL: str

INSTRUCTOR_COURSE_ID: int
PROFILE_ASSIGNMENT_ID: int
PROFILE_PAGES_COURSE_ID: int

DEFAULT_PROFILE_URL: str
LIVE_URL: str
HEADERS: dict
LIVE_HEADERS: dict
ACCOUNTS: list
ACCOUNT_IDS_BY_NAME: dict
ACCOUNT_ID: int
ROOT_ACCOUNT_ID: int
CONSTANTS: dict
CONSTANTS_FILE: str = 'constants.json'
MAX_PROFILE_IMAGE_SIZE: int = 400

SYLLABUS_REPLACEMENTS = [{
    'find': r'<p>The instructor will conduct [^.]*\(48 hours during weekends\)\.',
    'replace': r'<p>The instructor will conduct all correspondence with students related to the class in Canvas,'
               + ' and you should expect to receive a response to emails within 24 hours.'
}]


class LmFilter:
    replacements = [
        {
            'find': r'<p>\[Text[^\]]*by SME[^\]]*\]</p>',
            'replace': '',
        },

        {
            'find': r'\[[iI]nsert annotation for media\]',
            'replace': '',
        },
        {
            'find':
                r'<h3>\[Title for <span style="text-decoration: underline;"> optional </span>secondary media element\]</h3>',
            'replace': '',
        },
        {
            'find':
                r'<h3><strong>\[Title for \w+ category of LMs\]</strong></h3>',
            'replace': 'Materials',
        },
    ]

    @staticmethod
    def cbt_parents(item):
        return item.has_attr('class') and 'cbt-content' in item['class']

    @staticmethod
    def lm_narrative(item):
        is_content_block = item.has_attr('class') and 'cbt-content' in item['class']
        print(is_content_block)
        match = re.search(r'(\[\w*LM Narrative|LM Narrative])', item.text)
        if match:
            print(item)
            print(match)
        return is_content_block and match

    @classmethod
    def remove_lm_annotations(cls, text: str) -> str:
        """Summary
            Runs a list of regex replacements on html text of a
            Learning Material page (replacements, defined above)
    
        Args:
            text (str): An html string containing
            the body of a learning materials page
    
        Returns:
            str: An html string with the regexes run on it
        """
        # one liners to replace

        for replace in cls.replacements:
            find = re.compile(replace['find'], flags=re.MULTILINE)
            match = re.search(find, text)
            if match:
                text = re.sub(find, replace['replace'], text)

        # remove these sections
        soup = BeautifulSoup(text, 'lxml')
        bq = soup.find('blockquote')
        if bq and "SME" in str(bq):
            parent = single_filter(LmFilter.cbt_parents, bq.parents)
            parent.decompose()

        divs = soup.find_all('div')
        trash_divs = filter(LmFilter.lm_narrative, divs)
        if trash_divs:
            for div in trash_divs:
                div.decompose()

        out = str(soup.find('body'))
        out = re.sub(r'</?body>', '', out)
        return out


class CanvasApiLink:
    """
    This class handles api calls to the canvas api
    """
    headers: dict
    api_url: str
    account_id: int

    def __init__(
            self,
            headers: dict = None,
            api_url: str = None,
            account_id: int = None
    ) -> None:
        """

        Args:
            headers: The headers to use for requests when not otherwise specified
            api_url: The api url to use for requests
            account_id: The account id to use. Not currently used.
        """
        self.account_id = account_id
        self.headers = headers if headers else HEADERS
        self.api_url = api_url if api_url else API_URL
        self.account_id = account_id if account_id else ACCOUNT_ID

    def _query(self, func: callable, url: str, params: dict = None, **args):
        """
        Recurring code for all requests wrapper functions
        Args:
            func: the function to use for calls, assumed to be one of
            request.get, request.post, request.put, request.delete
            url: The url PAST the base API url
            params: any params to pass to the call
            **args: any additional params to pass to the call
        Returns:
            The json decoded data from the response

        """
        url = f'{self.api_url}/{url}'
        response = func(
            url,
            headers=args['headers'] if 'headers' in args else self.headers,
            params=params,
            **args)
        assert response.ok, response.text
        return response.json()

    def get(self, url: str, params: dict = None, **args):
        """
        Performs a canvas api call
        Args:
            url: any url to use after the canvas api base
            params: any params to pass to the requests.get call
            **args: and other args to pass to requests.get
        Returns:
            A dict or list holding the response from the canvas api

        """
        return self._query(requests.get, url=url, params=params, **args)

    def put(self, url: str, params: dict = None, **args):
        """
        Performs a canvas api put call
        Args:
            url: any url to use after the canvas api base
            params: any params to pass to the requests.get call
            **args: and other args to pass to requests.get
        Returns:
            A dict or list holding the response from the canvas api

        """
        return self._query(requests.put, url=url, params=params, **args)

    def get_paged_data(self, url: str, headers: dict = None, params: dict = None) -> list | None:
        """Summary
            returns a list of data from a get request, going through
            multiple pages of data requests as necessary

        Args:
            params: Any additional parameters to pass to the query
            url: The url path to query, not including the api_url
            headers: Headers for the request

        Returns:
            list: The paged data
        """
        headers = headers if headers else self.headers
        response = requests.get(f'{self.api_url}/{url}', headers=headers, params=params)
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
                    response = requests.get(next_page_link, headers=headers, params=params)
                    out = out + response.json()
                    break
                else:
                    next_page_link = ""

        return out


class BaseCanvasObject:
    """
    A base class for classes that talk to and hold data from canvas API,
    """
    api_link: CanvasApiLink
    _canvas_data: dict

    def __init__(self, data, headers=None, api_url=None, **kwargs):
        """
        Initializes the object
        Args:
            data: the canvas data this class is wrapping
            headers: the headers to use, passed to the api_link
            api_url: the api_url, passed to the api_link. CURRENTLY pulls from constant if not included
            **kwargs: all other args passed directly to api_link constructor
        """

        self._canvas_data = data if data is not None else {}
        self.api_link = BaseCanvasObject.new_api_link(headers=headers, api_url=api_url, **kwargs)

    def __getitem__(self, item):
        if item not in self._canvas_data:
            return None
        return self._canvas_data[item]

    def __setitem__(self, item, value):
        self._canvas_data[item] = value

    def __eq__(self, other):
        return self.id == other.id

    @staticmethod
    def new_api_link(headers=None, api_url=None, **kwargs):
        return CanvasApiLink(headers=headers, api_url=api_url, **kwargs)

    @property
    def id(self) -> int:
        """
        Course id
        Returns: canvas data course id

        """
        return self._canvas_data['id']


class Course(BaseCanvasObject):
    """
    A class to represent canvas courses and handle various canvas course based operations
    """
    CODE_REGEX = re.compile(r'([\-.\w]+)?_?(\w{4}\d{3})', re.IGNORECASE)

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)

    # Class Methods
    @classmethod
    def get_by_id(cls, id_: int) -> Self:
        """
        Gets a new Course instance by id populated with canvas data from the api

        Args:
            id_: THe id of the course to fetch and populate this course with

        Returns:
            A new Course
        """
        link = CanvasApiLink()
        data = link.get(f'courses/{id_}')
        return Course(data)

    @classmethod
    def get_all_by_code(cls, code: str, params: dict=None, term: 'Term' = None) -> List[Self]:
        return cls.get_by_code(code, params=params, term=term, return_list=True)

    @classmethod
    def get_by_code(
            cls,
            code: str,
            return_list: bool = False,
            params: dict = None,
            term: 'Term' = None
    ) -> Self | List[Self]:
        """
        Gets a course, or list of courses, by a course code
        Args:
            code: A course code of the forma TERMCODE_DEPT1234
            return_list: returns a list of all matching courses if true
            params: passes all additional params on to 'requests.get(params=)'
            term: the term to search within. Not used if not provided.


        Returns:
            A course or list of courses if return_list is true, matching the code
        """
        url = f"accounts/{ROOT_ACCOUNT_ID}/courses"
        params = params if params is not None else {}
        params['search_term'] = code
        if term is not None:
            params['enrollment_term_id'] = term.id
        link = CanvasApiLink()
        courses = link.get_paged_data(
            url,
            params=params
        )

        # if there are multiple courses, return by the most recently assigned a new ID
        if courses and len(courses) > 1:
            courses.sort(reverse=True, key=lambda course: course['id'])

        return list(
                map(lambda a: Course(a), courses)
            ) if return_list else Course(courses[0])

    @classmethod
    def publish_all(cls, courses: List[Self]):
        """
        Publishes a list of courses
        Args:
            courses: the list of courses to publish
        """
        url = f'{API_URL}/accounts/{ACCOUNT_ID}/courses'
        data = {
            'event': 'offer',
            # list of course ids
            'course_ids[]': list(map(lambda a: a['id'], courses))
        }
        response = requests.put(url, headers=HEADERS, data=data)
        if not response.ok:
            print(response)
            print(response.content)

    @cached_property
    def _code_match(self):
        return re.search(Course.CODE_REGEX, self._canvas_data["course_code"])

    # Properties
    @property
    def course_code(self) -> str | None:
        """
        The course code in the form PREFIX_DEPT1234
        """
        match = self._code_match
        if not match:
            return None
        prefix = match.group(1)
        course_code = match.group(2)
        return prefix + '_' + course_code

    @course_code.setter
    def course_code(self, value) -> None:
        """
        Sets the course code to value.
        """
        match = re.search(Course.CODE_REGEX, value)
        if not match:
            warnings.warn("Code does not match PREFIX_DEPT1234")

        self._canvas_data["course_code"] = value
        self._canvas_data["name"] = re.sub(self.CODE_REGEX, self._canvas_data['name'], value)
        # reset cache
        delattr(self, '_code_match')

    @property
    def base_code(self) -> str:
        if self._code_match:
            return self._code_match.group(2)
        return ""

    @property
    def code_prefix(self) -> str:
        if self._code_match:
            return self._code_match.group(1)
        return ""

    @property
    def is_blueprint(self) -> bool:
        """
        Is this course a blueprint?
        """
        return 'blueprint' in self._canvas_data and self._canvas_data['blueprint']

    @cached_property
    def associated_courses(self) -> List[Self] | None:
        """
        A list of associated courses if this is a blueprint. None otherwise.
        """
        if not self.is_blueprint:
            return None

        url = f"courses/{self.id}/blueprint_templates/default/associated_courses"
        courses = self.api_link.get_paged_data(url, params={"per_page": 50})

        return list(map(lambda a: Course(a), courses))

    @cached_property
    def subsections(self) -> list[dict]:
        url = f'courses/{self.id}/sections'
        sections = self.api_link.get(url, params={
            'include[]': 'enrollments'
        })
        return sections

    def get_potential_sections(self, term: 'Term') -> List[Self]:
        courses = Course.get_all_by_code(self.base_code, term=term)
        return courses

    def set_as_blueprint(self) -> None:
        url = f"courses/{self.id}"
        payload = {
            'course[blueprint]': True,
            'course[use_blueprint_restrictions_by_object_type]': 0,
            'course[blueprint_restrictions][content]': 1,
            'course[blueprint_restrictions][points]': 1,
            'course[blueprint_restrictions][due_dates]': 1,
            'course[blueprint_restrictions][availability_dates]': 1,
        }
        canvas_data = self.api_link.put(url, data=payload)
        self._canvas_data = canvas_data
        self.reset_cache()

    def unset_as_blueprint(self) -> None:
        url = f"courses/{self.id}"
        payload = {
            'course[blueprint]': False,
        }
        response = self.api_link.put(url, data=payload)
        self._canvas_data = response
        self.reset_cache()

    def reset_cache(self) -> None:
        if hasattr(self, 'subsections'):
            delattr(self, 'subsections')

        if hasattr(self, 'associated_courses'):
            delattr(self, 'associated_courses')

    def publish(self):
        """
        Publishes this course
        """
        Course.publish_all([self])



class Term(BaseCanvasObject):

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)

    @classmethod
    def get_by_code(
            cls,
            code: str,
            return_list: bool = False,
            workflow_state: str = 'all'
    ) -> Self | List[Self]:
        ct = CanvasApiLink(account_id=ROOT_ACCOUNT_ID)
        data = ct.get(f'accounts/{ROOT_ACCOUNT_ID}/terms', params={
            'workflow_state[]': workflow_state,
            'term_name': code
        })
        print(json.dumps(data))
        if 'enrollment_terms' not in data:
            warnings.warn(f'No enrollment terms found for {code}')
        terms = data['enrollment_terms']
        if not terms or len(terms) == 0:
            return None
        return Term(terms[0]) if not return_list else list(map(lambda a: Term(a), terms))

    @property
    def code(self) -> str:
        return self._canvas_data['name']

class Profile:
    """
    Class holding information needed to make a faculty pic and bio profile on course homepage
    Properties:
    user: The instructor user object
    bio: the text bio in html
    """
    user: dict = None
    bio: str = None

    def __init__(
            self,
            user: dict,
            bio: str,
            img_src: str,
            display_name: str = None,
            local_img_path: str = None,
            **kwargs
    ) -> None:
        """
        Args:
            user: The canvas api user
            bio: The biography of the user
            img_src: URL to the image
            local_img_path: Local path of the image, if saved
        """
        super().__init__(**kwargs)
        self.display_name = display_name
        self.user = user
        self.bio = bio
        self.img_src = img_src
        self.local_img_path = local_img_path


def load_constants(path=CONSTANTS_FILE, context=None):
    """
    Args:
        path: path to the constants file
        context: the context to set the constants in. Usually just this script. Will probably always be?
    Returns:
        a dict containing the loaded constants file
    """
    with open(path, 'r') as file:
        constants = json.load(file)

    if context is None:
        context = sys.modules[__name__]

    context.API_TOKEN = constants["apiToken"]
    context.API_URL = constants["apiUrl"]
    context.HTML_URL = re.sub('/api/v1', '', constants["apiUrl"])

    context.INSTRUCTOR_COURSE_ID = constants["instructorCourseId"]
    context.PROFILE_ASSIGNMENT_ID = constants["profileAssignmentId"]
    context.PROFILE_PAGES_COURSE_ID = constants["profilePagesCourseId"]

    context.DEFAULT_PROFILE_URL = f"{context.HTML_URL}/users/9230846/files/156109264/preview"
    context.LIVE_URL = constants["liveUrl"]

    # Authorize the request.
    context.HEADERS = {"Authorization": f"Bearer {context.API_TOKEN}"}
    context.LIVE_HEADERS = {"Authorization": f'Bearer {constants["liveApiToken"]}'}

    context.ACCOUNT_IDS_BY_NAME = dict()
    context.ACCOUNTS = requests.get(f'{API_URL}/accounts', headers=context.HEADERS).json()

    for account in context.ACCOUNTS:
        context.ACCOUNT_IDS_BY_NAME[account['name']] = account['id']

    context.ROOT_ACCOUNT_ID = context.ACCOUNT_IDS_BY_NAME['Unity College']
    context.ACCOUNT_ID = context.ACCOUNT_IDS_BY_NAME['Distance Education']
    context.CONSTANTS = constants

    return constants


def course_entry_callback(
        *,
        to_remove: list,
        course_string: str,
        window: tk.Tk,
        status_label: tk.Label):
    """Summary
        Callback to search for the course.
    Args:
        to_remove: A list of widgets to destroy on execution
        course_string: the string of the course to use
        window: the window we're working in
        status_label: Place to display
    """
    course_id = get_course_id_from_string(course_string)
    course = get_course_by_id(course_id)
    if not course_id:
        status_label.configure(text="Course Not Found")
        return False
    else:
        status_label.configure(text=f"Course Found\n{course['name']}")
        setup_main_ui(
            bp_course=Course.get_by_id(course_id),
            window=window,
            status_label=status_label)
        for widget in to_remove:
            widget.destroy()
        return True


def set_api_url(_api_url: str):
    global API_URL
    API_URL = _api_url
    return API_URL


def setup_main_ui(
        *,
        bp_course: Course,
        window: tk.Tk,
        status_label: tk.Label):
    """Summary
        Sets up the main workflow UI

    Args:
        bp_course: the course we're working with
        window: The widow to create UI in
        status_label: Description
    """
    # source_course_id = get_source_course_id(bp_id)
    # Create a progress bar
    progress_bar = ttk.Progressbar(
        window,
        orient="horizontal",
        length=200,
        mode="determinate")
    progress_bar.pack()

    def reset_and_import():
        course = bp_course
        course.unset_as_blueprint(),
        reset_course(course),
        # ID changes on reset so ge the new one
        course = Course.get_by_code(course.course_code)

        import_dev_course(course, progress_bar=progress_bar),
        course.set_as_blueprint()

    updates = [
        {
            'name': 'reset_and_import',
            'argument': 'reset',
            'message': "Do you want to reset this course and import DEV?",
            'func': reset_and_import,
            'hide': True,
        },
        {
            'name': 'update_syllabus',
            'argument': 'syllabus',
            'message': "Do you want to update syllabus language"
                       + " in this and DEV_?",
            'func': lambda: [
                update_syllabus(bp_course['id']),
                update_syllabus(get_source_course_id(bp_course['id']))]
        },
        {
            'name': 'remove_lm_annotations',
            'argument': 'lm',
            'message': "Do you want to remove "
                       + f"lm annotation placeholders from\n{bp_course['name']}?",
            'func': lambda: remove_lm_annotations_from_course(bp_course)

        },
        {
            'name': 'lock',
            'argument': 'lock',
            'message': 'Do you want to lock bluprint module items?',
            'func': lock_module_items_async(bp_course, progress_bar) if aiohttp else
            lambda: lock_module_items(bp_course, progress_bar)
        },
        {
            'name': 'associate',
            'message': "THIS STEP DOES NOTHING\n"
                       + "Associate courses by hand on Canvas site.\n"
                       + "This step only opens the page for you to do it.",
            'func': lambda: open_browser_func([f"{HTML_URL}/courses/{bp_course['id']}/settings"]),

        },
        {
            'name': 'sync',
            'hide': True,
            'message': 'Do you want sync associated courses? \n'
                       + 'NOTE: You must associate courses by hand before doing this',
            'error': 'There was a problem syncing\n{e}',
            'func': lambda: begin_course_sync(
                bp_course=bp_course,
                progress_bar=progress_bar,
                status_label=status_label),
        },

        {
            'name': 'download_profiles',
            'argument': 'download',
            'message': 'Do you want to '
                       + ' redownload the latest faculty profiles?',
            'func': lambda: get_faculty_pages(force=True)
        },

        {
            'name': 'profiles',
            'argument': 'profiles',
            'message': 'Do you want to update profiles in associated courses?',
            'error': 'There was a problem updating profile pages\n{e}',
            'func': lambda: replace_faculty_profiles(
                bp_course=bp_course,
                # get course by code in case it has changed
                courses=bp_course.associated_courses,
                window=window,
                progress_bar=progress_bar),
        },
        {
            'name': 'publish',
            'message': 'Do you want to publish associated courses?',
            'error': 'There was a problem publishing courses\n{e}',
            'func': lambda: Course.publish_all(bp_course.associated_courses)
        }
    ]

    asyncio.run(opening_dialog(
        updates=updates,
        window=window,
        status_label=status_label))


async def opening_dialog(
        *,
        window: tk.Tk,
        updates: list,
        status_label: tk.Label):
    """Summary
        Starts the process of creating an opening dialog window for the
        application

    Args:
        window: The base program window to render into
        updates: The Updates to run
        status_label: Description
    """
    ran_command_line = False
    value: Any = None
    for update in updates:
        if update['name'] in sys.argv \
                or 'argument' in update \
                and update['argument'] in sys.argv:
            value = await update['func']() if inspect.isawaitable(update['func']) else update['func']()
            ran_command_line = True
    if ran_command_line:
        return value
    else:
        checkboxes = []
        for update in updates:
            bool_var = tk.BooleanVar()
            update['run'] = bool_var
            if 'hide' in update and update['hide'] and "hidden" not in sys.argv:
                continue
            button = tk.Checkbutton(
                window,
                text=update['message'],
                onvalue=True,
                offvalue=False,
                variable=bool_var)
            checkboxes.append(button)
            button.pack()

        def callback(event=None):
            print(event)
            asyncio.run(handle_run(
                updates=updates,
                status_label=status_label))

        window.bind('<Return>', callback)

        button = tk.Button(
            master=window,
            text="Run",
            command=callback)
        button.pack()


async def handle_run(updates: list, status_label: tk.Label):
    """Summary
        Callback for when the user clicks 'run' on the opening dialog
        Iterates across the workflow options to check which are true
        and executes them in order.

    Args:
        updates: A list of dicts containing the callbacks
         and data for each checkbox / workflow step on the interface
        status_label: A label widget to update with status info
    """
    window = status_label.winfo_toplevel()
    for update in updates:
        try:
            print(update['name'], update['run'].get())
            if update['run'].get():
                status_label.config(text=f"Running {update['name']}")
                window.update()
                print(update)
                print(inspect.isawaitable(update['func']))
                if inspect.isawaitable(update['func']):
                    await update['func']
                else:
                    update['func']()
        except Exception as exception:
            messagebox.showerror(message=update['error'].format(
                e=str(exception)) + "\n" + traceback.format_exc())
            print(traceback.format_exc())
            raise exception

    status_label.config(text=f'Finished!')


def reset_course(course: Course):
    """Summary
        Resets the course and returns the reset version of the course
    Args:
        course: The course to reset

    Returns:
        TYPE: The new shiny, empty course
    """

    assert course, "Course does not exist"

    # ask for confirmation if we're not running this imported from another module
    if __name__ != "__main__" or messagebox.askyesno(
            title="Do You Want To Reset",
            message=f"Are you sure you want to reset {course['name']}?'"):

        url = f'{API_URL}/courses/{course["id"]}/reset_content'
        response = requests.post(url, headers=HEADERS)
        print(response)
        if response.ok:
            course['id'] = response.json()['id']
            return Course(response.json())

        else:
            raise Exception(response.json())
    return False


def import_dev_course(bp_course: Course, progress_bar=None):
    """
    Imports the dev version of a BP course into the BP course

    Args:
        bp_course: the bp course to import into
        progress_bar: an optional progress bar to update with progress
    """
    match = re.search(Course.CODE_REGEX, bp_course["course_code"])
    assert match, "This is not a course code " + bp_course["course_code"]
    prefix = match.group(1)
    course_code = match.group(2)
    assert prefix.upper() == 'BP', "Course code is not a blueprint"
    dev_course = Course.get_by_code(f"DEV_{course_code}")

    # if we're running this right from the script (instead of a unit test) prompt to confirm
    if course_code == "__main__":
        if not tk.messagebox.askyesno(
                f"Are you sure you want to import {dev_course['name']} into {bp_course['name']}?"):
            return None

    return import_course(bp_course, dev_course, progress_bar=progress_bar)


def import_course(dest_course: Course, source_course: Course, progress_bar=None) -> dict:
    """
        Copies source course into destination course. Returns the migration object
        once the migration is finished.
    Args:
        dest_course: The course to copy into
        source_course: The course to copy from
        progress_bar: An optional progress bar to update

    Returns:

    """
    payload = {
        "migration_type": "course_copy_importer",
        "settings[source_course_id]": source_course["id"]}

    url = f"{API_URL}/courses/{dest_course['id']}/content_migrations"
    response = requests.post(url, data=payload, headers=HEADERS)
    print(response)
    if response.ok:
        return poll_migration(migration=response.json(), progress_bar=progress_bar)


def generate_email(
        *,
        course: Course,
        courses: list,
        emails: list):
    """Summary
        Generates an email to a list of recipients and attempts to open
        outlook. On failure, copies to clipboard.

    Args:
        course (dict): The BP_ course we're operating on
        courses (list): A list of all the courses we've operated on
        emails (list): A list of all the emails to bcc
    """

    custom_email_path = "email_template.custom.html"
    email_path = custom_email_path if os.path.exists(custom_email_path) else "email_template.html"
    with open(email_path, 'r') as f:
        template = f.read()

    code = course["course_code"][3:]

    example_course = Course.get_by_id(
        courses[0]['id'] if courses
        else course['id'])
    print(json.dumps(example_course, indent=2))

    start_date = datetime.datetime.fromisoformat(
        example_course['term']["start_at"])
    start_date = start_date + datetime.timedelta(days=7)

    email_subject = \
        f'{course["course_code"][3:]} Section(s) Ready Notification'

    email_body = template.format(
        term={
            "name": example_course['term']['name'],
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

    except Exception as e:
        email_body = f"<p>bcc:{', '.join(emails)}</p>\n{email_body}"
        with open("email.htm", "w") as file:
            file.write(email_body)

        tk.messagebox.showerror(
            message="Error Generating Email."
                    + "Text has been copied to an html file which will open now.")

        webbrowser.open(
            f"file://{os.path.abspath('email.htm')}",
            new=1,
            autoraise=True)


def begin_course_sync(
        *,
        bp_course: Course,
        progress_bar: ttk.Progressbar,
        status_label: tk.Label) -> dict | None:
    """Summary
        Begins the sync process of the blueprint to its member course

    Args:
        bp_course: The blueprint course
        progress_bar: The progress bar to update. Not sure if we
        status_label: The status label to update with info
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
        f'{API_URL}/courses/{bp_course["id"]}'
        + '/blueprint_templates/default/migrations',
        headers=HEADERS,
        data=payload)

    if not response.ok:
        print(response)
        print(response.content)
        return None

    migration = response.json()
    poll_migration(
        migration,
        f'{API_URL}/courses/{bp_course["id"]}'
        + '/blueprint_templates/default/'
        + f'migrations/{migration["id"]}',
        status_label=status_label,
        progress_bar=progress_bar
    )


def poll_migration(
        migration: dict,
        migration_url: str | None = None,
        progress_bar: ttk.Progressbar | None = None,
        status_label: tk.Label | None = None,
        poll_interval: float = 2.0):
    """

    Args:
        migration(dict): a migration dict from canvas API
        migration_url(str): the url to poll, if different from that in the migration object
        progress_bar(ttk.Progressbar): an optional progress bar to update
        status_label(tk.Label): an optional status label to update
        poll_interval: the interval between polls, default 2 secs

    Returns:
        The migration dict

    """
    if migration_url is None:
        migration_url = migration['progress_url']
    response = requests.get(migration_url, headers=HEADERS)
    # poll the migration object until it is done
    while response.ok and migration['workflow_state'] in [
            'queued',
            'exporting',
            'imports_queued',
            'running']:

        print(response)
        print(migration)

        print(migration['workflow_state'])
        if status_label is not None:
            status_label.configure(text=f"{migration['workflow_state']}...")
        if progress_bar is not None and 'completion' in migration:
            update_progress_bar(progress_bar, migration['completion'])
        time.sleep(poll_interval)
        response = requests.get(migration_url, headers=HEADERS)
        if response.ok:
            migration = response.json()

    if progress_bar is not None:
        update_progress_bar(progress_bar, 100)
    print(response)
    print(response.content)
    return migration


def lock_module_items(course: Course, progress_bar: ttk.Progressbar | None = None):
    """Summary
        Locks all module items in a blueprint course

    Args:
        progress_bar: A progress bar object to update
        course: The course to lock items on
    """

    course_id = course.id
    modules = get_modules(course_id)

    total = 0
    for module in modules:
        total = total + len(module['items'])
    i = 0
    successes = 0
    failures = 0
    update_progress_bar(progress_bar, 0)
    for module in modules:
        for item in module['items']:
            url = f"{API_URL}/courses/{course_id}/" \
                  + "blueprint_templates/default/restrict_item"
            i = i + 1

            type_, id_ = get_item_type_and_id(item)
            if type_:
                response = requests.put(url, headers=HEADERS, data={
                    "content_type": type_,
                    "content_id": id_,
                    "restricted": True,
                })
                if response.ok:
                    successes = successes + 1
                    print(response.json())
                else:
                    failures = failures + 1
                    print(response)
                    print(response.text)
                    print(json.dumps(item, indent=2))

                update_progress_bar(progress_bar, i, total)

    update_progress_bar(progress_bar, 100, 100)
    return successes > 0 and failures == 0


async def lock_module_items_async(course, progress_bar=None):
    # Get modules using asynchronous API call
    modules = get_modules(course['id'])

    # Iterate over modules and items asynchronously

    total = 0
    for module in modules:
        total = total + len(module['items'])

    i = 0
    successes = 0
    failures = 0
    async with asyncio.TaskGroup() as tg:
        for module in modules:
            for item in module['items']:
                async def lock(to_lock):
                    nonlocal successes
                    nonlocal failures
                    nonlocal i
                    success = await lock_module_item_async(course, to_lock)
                    if success:
                        successes = successes + 1
                    elif success is not None:
                        failures = failures + 1
                    i = i + 1
                    update_progress_bar(progress_bar, i, total)

                tg.create_task(lock(item))
        if failures > 0:
            return False
        else:
            return True


async def lock_module_item_async(course, item):
    assert aiohttp
    url = f"{API_URL}/courses/{course['id']}/blueprint_templates/default/restrict_item"

    type_, id_ = get_item_type_and_id(item)
    print(item)

    data = {
        "content_type": type_,
        "content_id": id_,
        "restricted": True,
    }

    if type_:
        # Make asynchronous HTTP request to fetch page ID
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=HEADERS, data=data) as response:
                await response.text()
                if response.ok:
                    return True
                else:
                    return False
    else:
        return None


def get_item_type_and_id(item: dict) -> tuple[Any, Any | None] | tuple[None, None]:
    type_lut = {
        'Assignment': 'assignment',
        'Discussion': 'discussion_topic',
        'Quiz': 'quiz',
        'Attachment': 'attachment',
        'External Tool': 'external_tool',
        'File': 'file',
        'Page': 'wiki_page'
    }

    if item['type'] in type_lut:
        id_ = None
        type_ = type_lut[item["type"]]
        if type_ == "wiki_page":
            page_url = item["url"]
            response = requests.get(page_url, headers=HEADERS)
            if response.ok and response.status_code == 200:
                id_ = response.json()["page_id"]
        else:
            id_ = item["content_id"]

        return type_, id_
    else:
        return None, None


def get_source_course_id(course_id: int) -> int:
    """Summary
        Gets the id of the first course that migrated data into this one

    Args:
        course_id (int): The id of the course to check

    Returns:
        int: The course id of the source course

    """
    response = requests.get(
        f'{API_URL}/courses/{course_id}/content_migrations',
        headers=HEADERS)
    if not response.ok:
        return False
    migrations = response.json()
    # if there are no migrations return false
    if len(migrations) < 1:
        print("No imports found for course {course_id}")
        return False

    # sort by id descending so the first element is the latest created
    migrations.sort(reverse=True, key=lambda migration: migration['id'])
    return migrations[0]['settings']['source_course_id']


def remove_lm_annotations_from_course(course):
    """Summary
        Removes placeholder text for annotators from a course
        learning materials

    Args:
        course (TYPE): The course to remove

    Deleted Parameters:
        course (TYPE): The course to operate on
    """
    course_id = course['id']
    modules = get_modules(course_id)

    def lm_page_filter(item):
        return item['type'] == 'Page' \
            and re.search(r'Week \d+ Learning Materials', item['title'])

    for module in modules:
        # find an item in the module called "Week ? Learning Materials"
        lm_page = single_filter(lm_page_filter, module['items'])
        if lm_page:
            url = f"{API_URL}/courses/{course['id']}/pages/{lm_page['page_url']}"
            full_page = requests.get(url, headers=HEADERS).json()
            body = LmFilter.remove_lm_annotations(full_page['body'])
            print(lm_page['url'])
            data = {
                'wiki_page[body]': body
            }
            requests.put(
                lm_page['url'],
                headers=HEADERS,
                data=data)


def update_syllabus_text(text: str):
    """Summary
        Executes a series of find/replaces on the text of a syllabus

    Args:
        text (str): The syllabus body html

    Returns:
        TYPE: The syllabus with all operations performed
    """

    global SYLLABUS_REPLACEMENTS
    for replacement in SYLLABUS_REPLACEMENTS:
        text = re.sub(replacement['find'], replacement['replace'], text)
    return text


def update_syllabus(course_id: int):
    """Summary
        Updates the syllabus of a specific course id

    Args:
        course_id (int): The id of the course to operate on
    """
    url = f"{API_URL}/courses/{course_id}?include[]=syllabus_body"
    response = requests.get(url, headers=HEADERS)
    content = response.json()
    if not response.ok:
        return False
    print(content)
    syllabus = update_syllabus_text(content["syllabus_body"])
    response = requests.put(
        f'{API_URL}/courses/{course_id}',
        headers=HEADERS,
        data={
            "course[syllabus_body]": syllabus})
    print(response)


def single_filter(func, to_filter, default=None):
    """Summary
    Applies a filter and returns a single result
    Args:
        func (Any): The function passed to the filter() call
        to_filter (Any): Description
        default (None, optional): The default value to return if there are no elements

    Returns:
        Any: the filtered value
    """
    return next(filter(func, to_filter), default)


def get_modules(course_id: int | str) -> list:
    """Gets all modules including module item details

    Args:
        course_id (int): The ID of the course

    Returns:
        list: A list of module dicts
    """
    url: str = f"{API_URL}/courses/{course_id}/modules?" \
               + "include[]=items&include[]=content_details"
    print(url)
    return get_paged_data(url)


def update_progress_bar(
        progress_bar: ttk.Progressbar,
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
    if not progress_bar:
        return False
    ui_root = progress_bar.winfo_toplevel()
    ui_root.update_idletasks()
    ui_root.update()
    progress_bar["value"] = (value / maximum) * 100
    ui_root.update_idletasks()
    ui_root.update()


browser_button: tk.Button | None = None
email_button: tk.Button | None = None


def replace_faculty_profiles(
        *,
        bp_course: Course,
        courses: list,
        window: tk.Tk,
        progress_bar: ttk.Progressbar) -> list:
    """Summary
        Iterates across courses, grabs the instructor profile pages and updates
        the home page with bio and pic info.

    Args:
        window: The tk window.
        bp_course (dict): The blueprint course governing the courses.
        courses (list): A list of courses to update
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
                        + "does not have associated courses."
                        + "Do you want to just get the bio for this course?"):

            courses = [bp_course]
        else:
            return courses

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
        if len(profile.bio) < 5:
            error_text = error_text + \
                         f'{profile.user["name"]} does NOT have a bio we can find\n'
        else:
            bio_count = bio_count + 1
            if "email" in profile.user:
                emails.append(profile.user["email"])
            else:
                error_text = error_text + \
                             ("\nNo Email Found for " + profile.user["name"])

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
        generate_email(
            course=bp_course,
            courses=courses,
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
    Opens a list of urls in a web browser
    Args:
        urls (list): A list of urls
    """
    for url in urls:
        webbrowser.open(url, new=2, autoraise=False)


def save_bios(bios, path="bios.json"):
    """
    Saves faculty page api responses to a json file

    Args:
        bios (list): Description
        path (str, optional): Description
    """
    with open(path, 'w') as f:
        json.dump(bios, f, indent=2)


def get_faculty_pages(force=False):
    """
    Gets all pages from the "faculty pages" course

    Args:
        force (bool, optional): Forces a redownload. Otherwise just returns bios file.

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
            f"{LIVE_URL}/courses/{PROFILE_PAGES_COURSE_ID}"
            "/pages?per_page=50&include=body",
            LIVE_HEADERS)
        save_bios(pages)
    return pages


def get_course_by_id(course_id: int) -> Course:
    """Summary
        Gets a course by ID

    Args:
        course_id: ID of the course to get

    Returns:
        The course

    DeprecationWarning: Use Course.get_by_id(course_id) instead
    """
    warnings.warn("DeprecationWarning: Use Course.get_by_id instead")
    return Course.get_by_id(course_id)


def format_homepage(profile: Profile, course: Course, homepage: dict):
    """Summary
        Takes a faculty profile page, the course, and the homepage and returns
        the homepage filled in with faculty info and pic if able
    Args:
        profile: The profile dict for the user
        course: The course dict from canvas api
        homepage: The homepage dict from canvas api

    Returns:
        str: html string of the front page
    """

    # if it's cbt theme, run the new formatter
    text: str
    if "cbt-banner-header" in homepage['body']:
        text = format_homepage_curio(profile, homepage)
    else:
        with open("template.html", 'r') as f:
            template = f.read()
        text = template.format(
            course_title=homepage["title"] if "title" in homepage
            else f' Welcome to {course["name"]}',

            instructor_name=profile.display_name if profile.display_name else profile.user["name"],
            img_src=profile.img_src,
            bio=profile.bio)
        text = clean_up_bio(text)

    if not os.path.exists('profiles'):
        os.makedirs('profiles')
    profile_path = f'profiles/{profile.user["id"]}_{course["id"]}.htm'
    with open(profile_path, 'wb') as f:
        f.write(text.encode("utf-8", "replace"))

    return text


def clean_up_bio(html):
    """Summary
    Strips out empty html tags
    Args:
        html (str): The html of the faculty bio

    Returns:
        str: the html without empty paragraphs
    """
    html = re.sub(r'<p>\w*(&nbsp;)?\w*</p>', '', html)
    return html


def format_homepage_curio(profile: Profile, homepage: dict):
    """Summary
        Formats course home pages in the curio style, rather than the old style.
    Args:
        profile: Profile information for the instructor
        homepage: Canvas api home page for the course

    Returns:
        str: The formatted homepage content with instructor pic and bio
    """
    body = homepage['body']
    bio_body = profile.bio
    # change to api instead of site url
    img_data_url = re.sub('.com/', '.com/ap1/v1/', profile.img_src)
    body = re.sub(
        r'<p>\w*<span>\w*Instructor bio coming soon!\w*</span>\w*</p>',
        bio_body,
        body)
    # replace image
    find_profile_image = r'src="[^"]*"([^>]*) alt="male-profile-image-placeholder.png" data-api-endpoint="[^"]*"'
    print(re.search(find_profile_image, body))
    print("img src..." + profile.img_src)
    homepage = re.sub(
        find_profile_image,
        f'src="{profile.img_src}"\1data-api-endpoint="{img_data_url}"',
        body)

    return homepage


def get_course_profile(course: Course, pages: list[dict]):
    """
    Gets the instructor profile associated with a given course
    Args:
        course: The course to get the profile for
        pages: A list of faculty profile pages to search

    Returns:
        Profile: The profile information for the given course
    """
    instructor = get_canvas_instructor(course["id"])

    prompt = f'No instructor found for {course["name"]} ' \
             + 'do you want to to search for an instructor by name?'

    if not instructor:
        while tk.messagebox.askyesno(message=prompt):
            name = simpledialog.askstring(
                title="Name",
                prompt="Please enter the full user name"
                       "of the person you would like to find")

            result = requests.get(
                f"{API_URL}/accounts/self/users?search_term={name}",
                headers=HEADERS)
            if result.ok and len(result.json()) > 0:
                for user in result.json():
                    if tk.messagebox.askyesno(
                            message=f"Do you want to use {user['name']}?"):
                        instructor = user
                        break
                if instructor:
                    break
            else:
                prompt = f"No results found for {name}. " \
                         + "Do you want to search for another instructor?"
        if not instructor:
            return None

    profile = get_instructor_profile_from_pages(instructor, pages)

    if not profile or len(profile.bio) == 0:
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


def overwrite_home_page(profile: Profile, course: Course) -> str:
    """Summary
        Replaces the picture and bio element, if able
        of a course home page
     Args:
        profile: The faculty profile dictionary
        course: The course dictionary

     Returns:
        The url of the changed page
    """

    url = f'{API_URL}/courses/{course["id"]}/front_page'
    page_url = f'{HTML_URL}/courses/{course["id"]}/'
    print(page_url)
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        raise Exception(
            'Failed to get homepage of course: {}\nAre the associated sections still Syncing?'.format(
                response.status_code))

    homepage_html = response.json()['body']
    homepage = {"course_title": None, "body": homepage_html}
    soup = BeautifulSoup(homepage_html, 'html.parser')
    h2_tags = soup.find_all('h2')
    if len(h2_tags) > 0:
        homepage["title"] = h2_tags[0].text

    if profile:
        data = {'wiki_page[body]': format_homepage(
            profile, course, homepage)}

        response = requests.put(url, headers=HEADERS, data=data)
        print(response)
    else:
        print("instructor not found for this course; skipping")

    return page_url


def get_instructor_profile_from_pages(user: dict, pages: list[dict]) -> Profile | None:
    """Summary
    Gets an instructor profile from the faculty bios pages, or any similar page objects passed in
    Args:
        user: canvas api user object
        pages: A list of canvas api pages with titles that could be the use name

    Returns:
        Profile: Profile object
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

    potentials = []
    iterations = 0
    for func in filter_funcs:
        potentials = list(filter(func, pages))
        if len(potentials) > 0:
            break
        iterations = iterations + 1

    page = None

    # alert the user if there are no results
    if len(potentials) == 0:
        print("Potentials ")
        messagebox.showinfo(
            message=f"No profile found matching {user['name']}")
        return None

    # if we are more than two filters deep,
    # or there are more than one potential user,
    # prompt the user to confirm
    elif len(potentials) > 1 or iterations > 2:
        print(json.dumps(user, indent=2))
        print("_________________POTENTIALS______________________")
        print(json.dumps(potentials, indent=2))
        print("----------------------------------------------------")
        for potential in potentials:
            if "body" not in potential:
                continue
            if messagebox.askyesno(
                    message=f"No direct match found for {user['name']}."
                            f"Do you want to use {potential['title']}?"):
                page = potential
                break

    # otherwise pick the first result
    else:
        page = potentials[0]

    print(len(potentials))
    html = page["body"]
    soup = BeautifulSoup(html, 'html.parser')

    h4_tags = soup.find_all('h4')

    # Iterate over the h4 tags and find the next sibling paragraph tag
    paragraphs = []
    bio = ''
    for h4_tag in h4_tags:
        if "instructor" in h4_tag.text.lower():
            next_sibling = h4_tag.find_next_sibling('p')
            if not next_sibling:
                next_sibling = h4_tag.find_next_sibling('div')
            while next_sibling is not None:
                paragraphs.append(next_sibling.text)
                next_sibling = next_sibling.find_next_sibling('p')

    # Create the bio output
    for paragraph in paragraphs:
        bio = f"{bio}\n<p>{paragraph}</p>"

    # get display name just in case
    display_name: str | None = None
    for p in soup.find_all('p'):
        previous_p = p.find_previous_sibling('p')
        if "instructor" in p.text.lower() and previous_p is not None:
            print(previous_p.text)
            display_name = previous_p.text

    # get image output
    imgs = soup.find_all("img")
    img_src = None
    if imgs:
        img_src = imgs[-1]['src']
    print(img_src)
    return Profile(
        user=user,
        bio=bio,
        img_src=img_src,
        display_name=display_name
    )


def get_instructor_profile_submission(user) -> Profile:
    """Summary

    Args:
        user (dict): The instructor response dict from the canvas api

    Returns:
        dict: returns a dictionary containing the user, bio, image url, and a local path to the downloaded profile pic
    """
    url = f"{API_URL}/courses/{INSTRUCTOR_COURSE_ID}" \
          f"/assignments/{PROFILE_ASSIGNMENT_ID}/submissions/{user['id']}"
    response = requests.get(url, headers=HEADERS)
    submission = response.json()
    print(submission)
    bio = submission["body"] if (
            "body" in submission and submission["body"] is not None) else ""
    pic_path = ""
    if "attachments" in submission:
        for attachment in submission["attachments"]:
            url = attachment["url"]
            attachment_data = requests.get(url, headers=HEADERS)

            filename = attachment["filename"]
            with open(filename, 'wb') as f:
                f.write(attachment_data.content)
            filename = attachment["filename"]

            # handle doc
            if os.path.splitext(filename)[1] == ".docx" \
                    or os.path.splitext(filename)[1] == ".zip":
                doc = docx.Document(filename)
                with open(filename, 'rb') as f:
                    zip_file = zipfile.ZipFile(f)

                    for info in zip_file.infolist():
                        is_image = (
                                "jpg" in info.filename
                                or "png" in info.filename
                                or "jpeg" in info.filename)
                        if is_image:
                            pic_path = zip_file.extract(
                                info,
                                f"/{user['name']}{user['id']}"
                                + f"profile{os.path.splitext(info.filename)[1]}")

                for para in doc.paragraphs:
                    if len(para.text) > 10:
                        bio = bio + f"<p>{para.text}</p>\n"

            # if it's an attached image
            elif os.path.splitext(filename)[1] in ['.jpg', '.jpeg', '.png']:
                with open(
                        f"{user['name']}"
                        + f"{user['id']}profile"
                        + f"{os.path.splitext(filename)[1]}",
                        "wb") as f:
                    f.write(attachment_data.content)
                    pic_path = os.path.realpath(f.name)

        # todo: upload resized profile pic and populate upload_url
    img_upload_url = ""
    if len(pic_path) > 0:
        pic_path = resize_image(pic_path, MAX_PROFILE_IMAGE_SIZE)
        img_upload_url = ""  # upload_image(pic_path, instructor_course_id)

    img_src = img_upload_url if \
        img_upload_url and len(img_upload_url) > 0 \
        else DEFAULT_PROFILE_URL

    return Profile(user=user, bio=bio, img_src=img_src, local_img_path=pic_path)


def resize_image(path, max_width):
    """Summary
    Resizes an image to a maximum width

    Args:
        path: Path to the original image
        max_width: the maximum width to scale the image to

    Returns:
        The path to the resized image on disk
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


# TODO: Finish this when it's not crunch time.
def upload_image(pic_path: str, course_id: int) -> dict[str, str] | None:
    # Process and upload user image
    # get the correct folder id
    url = f"{API_URL}/courses/{course_id}/folders/by_path/Images/"
    response = requests.get(url, headers=HEADERS)
    folders = response.json()
    upload_folder = folders[-1]

    # upload the file
    file_url = f"{API_URL}/courses/{course_id}/files"
    print(f"uploading {pic_path} to {file_url}")
    data = {
        "name": os.path.basename(pic_path),
        "no_redirect": True,
        "parent_folder_id": upload_folder["id"],
        "on_duplicate": "overwrite"
    }

    response = requests.post(file_url, data=data, headers=HEADERS)

    if response.ok:
        response_data = response.json()
        files = {"file": open(pic_path, 'rb')}
        url = response_data["upload_url"]
        response = requests.post(url, files=files, data=response_data['upload_params'])
        print(response)
        if not response.ok:
            print(response.text)
            return None

        if response.is_redirect:
            response = requests.Session().send(response.next)

        return response.json()


def get_instructor_page(user: dict | str):
    """Gets the page in Faculty Bios course that matches this instructor

    Args:
        user(dict | str): A dictionary containing the json user response from canvas or the instructor's name as a str

    Returns:
        list: A list of all matches
    """
    search_string = user if type(user) is str else user['name']

    url = f"{API_URL}/courses/{PROFILE_PAGES_COURSE_ID}/pages" \
          + f"?per_page=999&search_term={urllib.parse.quote(search_string)}"

    pages = get_paged_data(url)
    for page in pages:
        print(page["title"])
    return pages


def get_canvas_course_home_page(course_id: int):
    """Gets the home page for a course based on id

    Args:
        course_id (int): The id of the course

    Returns:
        dict: The home page of the course from canvas api
    """
    # Make the request to the Canvas LMS course home page.
    url = f"https://unity.instructure.com/courses/{course_id}"
    response = requests.get(url, headers=HEADERS)
    return response.content


def get_canvas_instructor(course_id: int) -> dict | None:
    """Gets the instructor for a given canvas course based on id

    Args:
        course_id (int): The id of the course

    Returns:
        TYPE: Description
    """
    url = f"{API_URL}/courses/{course_id}/users?" + \
          "enrollment_type=teacher"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return None

    users = response.json()
    for user in users:
        return user

    return None


def get_paged_data(url: str, headers=None, params=None) -> list | None:
    """Summary
        returns a list of data from a get request, going through
        multiple pages of data requests as necessary

    Args:
        params(dict): Any additional parameters to pass to the query
        url (str): The url to query
        headers (dict, optional): Headers for the request

    Returns:
        list: Description
    """
    if headers is None:
        headers = HEADERS
    response = requests.get(url, headers=headers, params=params)
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
                response = requests.get(next_page_link, headers=headers, params=params)
                out = out + response.json()
                break
            else:
                next_page_link = ""
    print(len(out))

    return out


def get_course_id_from_string(course_string: str):
    """Summary
        Gets a course id from a course code matching
        the course code format (e.g. AAA0000)
    Args:
        course_string(str): The string to match
    Returns:
        int: the course id if it matches a regex for course id
    """
    id_match = re.search(r'(\d{7}\d*)', course_string)
    course_name_match = re.search(r'(\w+_\w{4}\d{3})', course_string)
    course_root_name_match = re.search(r'(\w{4}\d{3})', course_string)
    if id_match:
        print(id_match)
        return int(id_match.group(1))
    elif course_name_match:
        print(course_name_match)
        return Course.get_by_code(course_name_match.group(1))['id']
    elif course_root_name_match:
        return Course.get_by_code(f"BP_{course_root_name_match.group(1)}")['id']
    else:
        return None

def main():
    """Summary
        Main loop. Opens an interface you can perform various
        course publishing operations with.
    """
    load_constants(CONSTANTS_FILE, sys.modules[__name__])
    window = tk.Tk()
    window.geometry("600x400")
    initial_value = None
    used_clipboard = False
    if len(sys.argv) > 1:
        initial_value = sys.argv[1]
    else:
        try:
            initial_value = get_course_id_from_string(window.clipboard_get())
            used_clipboard = True
        except tk.TclError:
            print("Clipboard empty")

    label = tk.Label(
        window,
        text="Enter the course code (e.g. BP_ANIM305) or id\n"
             + "(if you are seeing auto-text, you already had a course code "
             + "or id copied)")
    label.pack()

    course_string_var: StringVar = tk.StringVar(
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

    if not used_clipboard and initial_value is not None:
        callback()
    window.mainloop()


if __name__ == "__main__":
    main()
