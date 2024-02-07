from functools import cached_property
import warnings
import inspect

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


class ReplaceException(BaseException):
    pass


class CourseNotFoundException(BaseException):
    pass


class Replacement:
    def __init__(self, find: str, replace: str | Callable, success_tests: list):
        self.find = find
        self.replace = replace
        self.tests = success_tests

    @staticmethod
    def in_test(to_match, phase=None, msg=None):
        msg = to_match if msg is None else msg

        def func(text):
            return to_match in text

        return func, phase, msg

    @staticmethod
    def re_search(expression, true_if_false=False, phase=None, msg=None):
        msg = expression if msg is None else msg

        def func(text):
            match = re.search(expression, text)
            out = False
            if match is not None:
                if true_if_false:
                    out = False
                else:
                    out = match
            print(out)
            return out

        return func, phase, msg

    @staticmethod
    def not_in_test(to_match, phase=None, msg=None):
        msg = to_match if msg is None else msg

        def func(text):
            return to_match not in text

        return func, phase, msg

    def pre_check(self, text: str):
        return self._check_tests(text, phase='pre')

    def post_check(self, text: str):
        def callback(msg):
            raise ReplaceException(msg)

        return self._check_tests(text, 'post', callback)

    def _check_tests(self, text: str, phase=None, on_fail: Callable = None):
        for test, phase_, msg in self.tests:
            if (phase and phase == phase_) or not phase_ or not phase:
                result, msg = test(text), msg
                if not test(text):
                    if on_fail:
                        on_fail(msg)
                    return result, msg
        return True, "all tests passed"

    def fix(self, source_text) -> (bool, str):
        no_need_to_run, msg = self.pre_check(source_text)

        if no_need_to_run:
            print("all tests passed, no need to apply fix " + self.find)
            return False

        groups: tuple
        match = re.search(self.find, source_text)
        if not match:
            return False

        if callable(self.replace):
            replace = self.replace
            replace(match, source_text)

        # backup_text = source_text
        out_text = re.sub(self.find, self.replace, source_text)
        result, msg = self.post_check(out_text)
        if not result:
            raise ReplaceException(msg)

        return out_text


class FixSet:
    replacements = []

    @classmethod
    def fix(cls, source_text: str) -> str:
        out_text = source_text
        for replacement in cls.replacements:
            print(f"Running {replacement.find} --> {replacement.replace}")
            fixed_text = replacement.fix(out_text)
            if fixed_text:
                out_text = fixed_text

        return out_text


class SyllabusFix(FixSet):
    replacements = [
        Replacement(
            find=r'(after you.ve )viewed( the <a title="Course Overview")',
            replace=r'\1agreed to\2',
            success_tests=[
                Replacement.in_test(r've agreed to the'),
            ]
        ),
        Replacement(
            find=r'''To access a discussion's grading.*and then click "show rubric".''',
            replace=r'''To access a discussion's grading rubric, click on the "View Rubric" button in the discussion directions and/or the "Dot Dot Dot" (for screen readers, titled "Manage this Discussion") button in the upper right corner of the discussion, and then click "show rubric".''',
            success_tests=[
                Replacement.in_test(r'"View Rubric" button')
            ]
        ),
        Replacement(
            find=r'''<div class="cbt-table">\s*<p>Please make sure that.*library webpage for more information.</p>''',
            replace='<div class="cbt-table">',
            success_tests=[
                Replacement.re_search(r'>\s*Copyright\s*<', phase="pre")
            ]
        ),
        Replacement(
            find=r'(support your learning\.\s*</p>\s*</td>\s*</tr>)(\s*<tr style="height: 178px;">)',
            replace=r'''\1
<tr style="height: 118px;">
<td style="width: 99.8918%; height: 118px;">
<h3><strong>Copyright</strong></h3>
<p>Please make sure that any photographs or materials used for class projects are not copyright protected. If you have any questions about copyright law, please go to the Unity Environmental University library webpage for more information.</p>
</td>
</tr>
\2''',
            success_tests=[
                Replacement.re_search(r'<h3(.*)Copyright(.*)h3>'),
            ]
        ),
        Replacement(
            find=r'(<th[^>]*>)[\s\n]*Assignments[\s\n]*</th>',
            replace=r'\1Letter Grade</th>',
            success_tests=[
                Replacement.in_test('Letter Grade</th>')
            ]
        ),
        Replacement(
            find=r'(<th[^>]*>)[\s\n]*Due date[\s\n]*</th>',
            replace=r'\1Percent</th>',
            success_tests=[
                Replacement.in_test('Percent</th>')
            ]
        ),
        Replacement(
            find=r'(<th[^>]*>)[\s\n]*Weight[\s\n]*</th>',
            replace=r'\1</th>',
            success_tests=[
                Replacement.not_in_test('Weight</th>')
            ]
        ),
        Replacement(
            find=r'<p>The instructor will conduct [^.]*\(48 hours during weekends\)\.',
            replace=r'<p>The instructor will conduct all '
                    + r'correspondence with students related to the class in Canvas,'
                    + ' and you should expect to receive a response to emails within 24 hours.',
            success_tests=[
                Replacement.not_in_test('48 hours'),
                Replacement.in_test('you should expect')
            ]
        ),
        Replacement(
            find='EducationGenerative',
            replace='Education Generative',
            success_tests=[
                Replacement.not_in_test('EducationGenerative'),
                Replacement.in_test('Education Generative')
            ]
        ),
        Replacement(
            find=r'(</tr>.*\n)(.*)(<tr.*\n.*<td.*\n.*Copyright\s*</strong>)',
            replace=r'''\1
<tr>
<td style="width: 99.8918%;">
<h4><strong>
Guidelines for Using Generative Artificial Intelligence [AI] in this Course:
</strong></h4>
<p>Using generative AI must be done with an understanding of the
<a class="inline_disabled" href="https://unity.instructure.com/courses/3266650/pages/gen-ai-student-policy" target="_blank" rel="noopener">
<strong>Unity Distance Education Generative Artificial Intelligence Policy for Students</strong>
</a>, which spells out acceptable and unacceptable uses of generative AI in your studies in the Unity Distance Education Program.</p>
<p><strong>Please read this policy before completing coursework using generative AI in this course.</strong></p>
<ul>
<li>In this course, you may be encouraged to explore employing generative AI tools to improve your understanding of course content.
<em>Potentially permitted uses of generative AI are detailed in the above policy.</em></li>
<li>There also may be specific work in which content produced by generative AI will not be accepted in this course.<em> It will be specifically noted in the course materials when you are not permitted to submit work produced by generative AI.</em></li>
<li>When no explicit statement about the use of generative AI is provided in an assignment, these tools are permitted.</li>
</ul>
<p>You are encouraged to contact your instructor if you have questions about how to use generative AI effectively to support your learning.</p>
</td>
</tr>
\3''',
            success_tests=[
                Replacement.in_test('generative AI effectively to support'),
                Replacement.re_search(r'>\s*Copyright\s*<')
            ]
        ),
    ]


class EvalFix(FixSet):
    @classmethod
    def find_content(cls, course: 'Course') -> List['BaseContentItem']:
        return course.get_pages_by_name('Course Evaluation')

    # Deprecated, there is no content here anymore
    replacements = []


class IntroFixSet(FixSet):
    @classmethod
    def find_content(cls, course: 'Course') -> List['BaseContentItem']:
        return course.get_discussions('Introductions')

    replacements = [
        Replacement(
            find=r'''<h1 class="discussion-title">''',
            replace=r'''<h1>''',
            success_tests=[
                Replacement.not_in_test('discussion_title'),
                Replacement.re_search(r'<h1>.*</h1>')
            ]
        )
    ]


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
        # replace one liners. TODO: migrate this to new Replacement model
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


class ResourcesFixSet(FixSet):
    @classmethod
    def find_content(cls, course: 'Course') -> list['Page']:
        return course.get_pages_by_name('Student Support Resources')

    replacements = [
        Replacement(
            find=r'<p>(<strong>Your advisor.*)</p>',
            replace=r'''<p><strong>Your advisor</strong> can support you with any college policies or procedures and help inform you of and <a href="https://online.unity.edu/support/"> support you with any of the college's resources.</a></p>''',
            success_tests=[
                Replacement.in_test(r'''<p><strong>Your advisor</strong> can support you with any college policies or procedures and help inform you of and <a href="https://online.unity.edu/support/"> support you with any of the college's resources.</a></p>'''),
            ]
        ),
        Replacement(
            find=r'''<p><strong>TutorMe.*</p>''',
            replace=r'<p><strong>Pear Deck Tutor (see TutorMe link in navigation)</strong>'
                    r'&nbsp;can support you with any course subject matter '
                    r'or assessment specific question you may have.</p>',
            success_tests=[
                Replacement.in_test('Pear Deck Tutor'),
                Replacement.not_in_test('<strong>TutorMe')
            ]
        ),
        Replacement(
            find=r"<p><strong>Your instructor.*<a.*</p>",
            replace=r'''<p><strong>Your instructor (click "Help" in Navbar and then "Ask instructor a question")'''
                    r'''</strong>&nbsp;can support you with any course subject matter '''
                    r'''or assessment specific question you may have.</p>''',
            success_tests=[
                Replacement.not_in_test(
                    r'''Your instructor (click "Help" in Navbar and then "Ask instructor '''
                    '''a question")</strong>&nbsp;can support you with any college policies or '''
                    '''procedures and help inform you of and <a href="https'''
                    '''://online.unity.edu/support/">support you with any of the college's '''
                    '''resources.</a>'''
                )
            ]
        ),
        Replacement(
            find=r'[.]</a>[.]</p>',
            replace=r'</a>.</p>',
            success_tests=[
                Replacement.not_in_test(r'.</a>.</p>')
            ]
        ),
        Replacement(
            find=r'matteror',
            replace=r'matter or',
            success_tests=[
                Replacement.not_in_test(r'matteror')
            ]
        )
    ]


class OverviewFixSet(FixSet):
    @classmethod
    def find_content(cls, course: 'Course') -> list['Page']:
        pages = []
        for i in range(1, 9):
            pages += course.get_pages_by_name(f'Week {i} Overview')
        return pages

    replacements = [
        Replacement(
            find=r'<h2.*>.*[lL]earning [oO]bjectives.*</h2>',
            replace=r'<h2>Weekly Objectives</h2>',
            success_tests=[
                Replacement.in_test('<h2>Weekly Objectives</h2>')
            ])
    ]


class FrontPageFixSet(FixSet):
    @classmethod
    def find_content(cls, course: 'Course') -> list['Page']:
        return [course.front_page]

    replacements = [
        Replacement(
            find=r'<div class="col-md-6 col-sm-12" data-context-menu="remove" data-canhavechild="true">\n'
                 r'(<p><span>Instructor bio coming soon!</span></p>\n)'
                 r'(</div>)',
            replace=r'<div class="cbt-instructor-bio col-md-6 col-sm-12" '
                    r'data-context-menu="remove" data-canhavechild="true">\n\1\2',
            success_tests=[
                Replacement.in_test('cbt-instructor-bio')
            ]),
    ]


FIXES_TO_RUN = [OverviewFixSet, ResourcesFixSet, FrontPageFixSet, IntroFixSet]


class CanvasApiLink:
    """
    This class handles api calls to the canvas api
    """

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

        self.account_id = account_id if account_id else ACCOUNT_ID
        """
        The canvas account to use when making requests to the canvas api
        """

        self.headers = headers if headers else HEADERS
        """
        the default headers to send to the canvas api when making requests
        """

        self.api_url = api_url if api_url else API_URL
        """
        The canvas api base url
        """

    @property
    def html_url(self):
        """
        Returns:
        The full base html url of the canvas site
        """
        return re.sub('/api/v1', '', self.api_url)

    def _query(self, func: callable, url: str, **args):
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
        url = f"{self.api_url}/{url}"
        print('calling ' + url)
        if 'headers' not in args:
            args['headers'] = self.headers
        response = func(url, **args)
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

    def delete(self, url: str, params: dict = None, **args):
        return self._query(requests.delete, url=url, params=params, **args)

    def put(self, url: str, params: dict = None, data=None, **kwargs):
        """
        Performs a canvas api put call
        Args:
            data: data to put
            url: any url to use after the canvas api base
            params: any params to pass to the requests.get call
            **kwargs: and other args to pass to requests.get
        Returns:
            A dict or list holding the response from the canvas api

        """
        return self._query(requests.put, url=url, params=params, data=data, **kwargs)

    def post(self, url, params: dict = None, data=None, **kwargs):
        return self._query(requests.post, url=url, params=params, data=data, **kwargs)

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
    A base class for classes that talk to and hold data from canvas API
    """

    _id_property = 'id'
    """
    The field name of the id of the canvas object type
    """

    _name_property = None
    """
    The field name of the primary name of the canvas object type
    """

    _content_url_template = None
    """
    A templated url to get a single item
    """

    _all_content_url_template = None
    """
    A templated url to get all items
    """

    def __init__(self, data, headers=None, api_url=None, api_link=None, account_id=None, **kwargs):
        """
        Initializes the object
        Args:
            data: the canvas data this class is wrapping
            headers: the headers to use, passed to the api_link
            api_url: the api_url, passed to the api_link. CURRENTLY pulls from constant if not included
            **kwargs: all other args passed directly to api_link constructor
        """
        self.account_id = account_id
        """
        The account ID that this object primarily lives in. Passed as a default to the api link.
        """

        self._canvas_data: dict = data if data is not None else {}
        """
        A dict holding the decoded json representation of the object in canvas
        """

        self.api_link: CanvasApiLink = api_link if api_link is not None else (
            BaseCanvasObject.new_api_link(headers=headers, api_url=api_url, account_id=account_id))
        """
        The api link to Canvas that all canvas api calls are made through.
        """

    def __getitem__(self, item):
        if item not in self._canvas_data:
            return None
        return self._canvas_data[item]

    def __eq__(self, other):
        return self.id == other.id

    @property
    def content_url_path(self):
        return self._content_url_template.format(content_id=self.id, account_id=self.account_id)

    @property
    def html_content_url(self):
        url = self.api_link.api_url + '/' + self.content_url_path

        return re.sub('api/v1/', '/', url)

    @property
    def api_content_url(self):
        raise ValueError(f"property content_link is not defined for {type(self).__name__}")

    @staticmethod
    def new_api_link(headers=None, api_url=None, account_id=None):
        return CanvasApiLink(headers=headers, api_url=api_url, account_id=account_id)

    @classmethod
    def get_by_id(cls, course: 'Course', content_id: int, account_id=None, params: dict = None) -> Self:
        return cls(course, cls._get_data_by_id(
            course=course,
            content_id=content_id,
            account_id=account_id,
            params=params,
        ))

    @classmethod
    def _get_data_by_id(cls, course: 'Course', content_id: int, account_id=None, params: dict = None) -> dict:
        link = course.api_link
        return link.get(cls.get_url_path_from_ids(course_id=course.id, content_id=content_id, account_id=account_id), params=params)

    @classmethod
    def get_all(cls, course: 'Course' = None, params: dict = None) -> list[Self]:
        link = course.api_link
        data = link.get_paged_data(cls.get_all_url(course_id=course.id), params=params)
        return [cls(course, item) for item in data]

    @classmethod
    def get_url_path_from_ids(cls, course_id: int, content_id: int, account_id: int = None):
        return cls._content_url_template.format(course_id=course_id, content_id=content_id, account_id=account_id)

    @classmethod
    def get_all_url(cls, course_id: int, account_id=None):
        return cls._all_content_url_template.format(course_id=course_id, account_id=account_id)

    @property
    def id(self) -> int:
        return self._canvas_data[self._id_property]

    @property
    def name(self) -> str:
        return self[self._name_property]

    def _save_data(self, data: dict) -> dict:
        return self.api_link.put(self.content_url_path, data=data)

    def delete(self) -> dict:
        return self.api_link.delete(self.content_url_path)


class BaseContentItem(BaseCanvasObject):
    _body_property = None

    def __init__(self, course: 'Course', data, **kwargs):
        super().__init__(data, **kwargs)
        self._course = course

    @staticmethod
    def clear_added_content_tags(text: str):
        out = re.sub(r'</?link[^>]*>', '', text)
        out = re.sub(r'</?script[^>]*>', '', out)
        return out

    @property
    def body(self) -> str | None:
        if self._body_property is None:
            return None
        else:
            return self.clear_added_content_tags(
                self._canvas_data[self._body_property])

    @property
    def content_url_path(self):
        return self._content_url_template.format(course_id=self.course.id, content_id=self.id)

    @property
    def course(self) -> 'Course':
        return self._course

    def update_content(self, text: str = None, name: str = None):
        data = {}
        if text and self._body_property:
            self._canvas_data[self._body_property] = text
            data[self._body_property] = text

        if name and self._name_property:
            self._canvas_data[self._name_property] = name
            data[self._name_property] = text

        return self._save_data(data)

    def delete(self):
        return self.api_link.delete(self.content_url_path)


class Discussion(BaseContentItem):
    _name_property = 'title'
    _body_property = 'message'
    _content_url_template = "courses/{course_id}/discussion_topics/{content_id}"
    _all_content_url_template = "courses/{course_id}/discussion_topics"


class Assignment(BaseContentItem):
    _name_property = 'name'
    _body_property = 'description'
    _content_url_template = "courses/{course_id}/assignments/{content_id}"
    _all_content_url_template = "courses/{course_id}/assignments"


class Quiz(BaseContentItem):
    _name_property = 'title'
    _body_property = 'description'
    _content_url_template = "courses/{course_id}/quizzes/{content_id}"
    _all_content_url_template = "courses/{course_id}/quizzes"

    @property
    def due_at(self):
        if self._canvas_data['due_at'] is None:
            return None

        return datetime.datetime.fromisoformat(self._canvas_data['due_at'])

    def set_due_at(self, due_at: datetime.datetime):

        self._save_data({
            'quiz[due_at]': due_at.isoformat()
        })
        self._canvas_data['due_at'] = due_at.isoformat()

    def due_at_timedelta(self, **timedelta):

        if self.due_at is None:
            return None

        due_at = self.due_at + datetime.timedelta(**timedelta)
        self.set_due_at(due_at)


class Page(BaseContentItem):
    _id_property = 'page_id'
    _name_property = 'title'
    _body_property = 'body'
    _content_url_template = "courses/{course_id}/pages/{content_id}"
    _all_content_url_template = "courses/{course_id}/pages/"

    @property
    def revisions(self):
        out = self.api_link.get_paged_data(f'{self.content_url_path}/revisions')
        return out

    def revert_last_changeset(self, steps_back=1):
        revisions = self.revisions
        revisions.sort(key=lambda a: a['revision_id'], reverse=True)
        if len(revisions) <= steps_back:
            warnings.warn(f"tried to revert {self.name} but there isn't a previous revision")
            return None
        # the first one is the latest change, if we just want revert
        revision = revisions[steps_back]
        self.apply_revision(revision)

    def reset_content(self, revision_id=1):
        revisions = self.revisions
        revision = next(filter(lambda a: a['revision_id'] == revision_id, revisions), None)
        if revision is None:
            raise ValueError(f'No revision found for {revision_id}')
        self.apply_revision(revision)

    def apply_revision(self, revision):
        revision_id = revision['revision_id']
        result = self.api_link.post(f"{self.content_url_path}/revisions/{revision_id}", params={
            'revision_id': revision_id
        })
        self._canvas_data[self._body_property] = result['body']
        self._canvas_data[self._name_property] = result['title']

    def update_content(self, text: str = None, name: str = None) -> dict:
        data = {}
        if text:
            self._canvas_data[self._body_property] = text
            data['wiki_page[body]'] = text
        if name:
            self._canvas_data[self._name_property] = name
            data['title'] = name

        return self._save_data(data)


class Rubric(BaseContentItem):
    _name_property = 'title'
    _body_property = None
    _content_url_template = "courses/{course_id}/rubrics/{content_id}"
    _all_content_url_template = "courses/{course_id}/rubrics"

    @property
    def associations(self, reload: bool = False) -> list['RubricAssociation']:
        if 'associations' in self._canvas_data and reload:
            return self._body_property['associations']

        data: dict = self._get_data_by_id(
            course=self.course,
            content_id=self.id,
            params={'include': ['associations']}
        )
        associations: list[RubricAssociation] = [RubricAssociation(self.course, ra) for ra in data['associations']]
        self._canvas_data['associations'] = associations
        return associations


class RubricAssociation(BaseContentItem):
    _name_property = None
    _content_url_template = "courses/{course_id}/rubric_associations/{content_id}"
    _all_content_url_template = "courses/{course_id}/rubric_associations"

    @property
    def use_for_grading(self) -> bool:
        return self._canvas_data['use_for_grading']

    def set_use_for_grading(self, value):
        self._canvas_data['use_for_grading'] = value
        result = self._save_data({
            'rubric_association[use_for_grading]': value
        })
        return result


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


class Course(BaseCanvasObject):
    """
    A class to represent canvas courses and handle various canvas course based operations
    """
    _name_property = 'name'
    CODE_REGEX = re.compile(r'([\-.\w^]+[^_])?_?(\w{4}\d{3})', re.IGNORECASE)

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)

    # Class Methods
    @classmethod
    def get_by_id(cls, id_: int, params=None, account_id=None, link: CanvasApiLink = None) -> Self:
        """
        Gets a new Course instance by id populated with canvas data from the api

        Args:
            account_id: The base account ID to use when looking, if relevant
            link: the CanvasApiLink to use for the transaction
            id_: THe id of the course to fetch and populate this course with
            params: any parameters to pass to the request

        Returns:
            A new Course
        """
        if link is None:
            link = CanvasApiLink(account_id=account_id)
        data = link.get(f'courses/{id_}', params=params)
        return Course(data)

    @classmethod
    def get_all_by_code(
            cls,
            code: str | None,
            params: dict = None,
            link: CanvasApiLink = None,
            term: 'Term' = None) -> List[Self]:

        return cls.get_by_code(code, params=params, term=term, link=link, return_list=True)

    @classmethod
    def get_by_code(
            cls,
            code: str | None,
            return_list: bool = False,
            params: dict = None,
            link: CanvasApiLink = None,
            term: 'Term' = None
    ) -> Self | List[Self]:
        """
        Gets a course, or list of courses, by a course code
        Args:
            link:
            code: A course code of the forma TERMCODE_DEPT1234
            return_list: returns a list of all matching courses if true
            params: passes all additional params on to 'requests.get(params=)'
            term: the term to search within. Not used if not provided.


        Returns:
            A course or list of courses if return_list is true, matching the code
        """
        courses = None
        for account in ACCOUNT_IDS_BY_NAME:
            account_id = ACCOUNT_IDS_BY_NAME[account]
            url = f"accounts/{account_id}/courses"
            params = params if params is not None else {}
            if code is not None:
                params['search_term'] = code
            if term is not None:
                params['enrollment_term_id'] = term.id
            link = link if link is not None else CanvasApiLink()
            courses = link.get_paged_data(
                url,
                params=params
            )
            if courses and len(courses) > 0:
                break

        if courses is None or len(courses) == 0:
            return None

        # if there are multiple courses, return by the most recently assigned a new ID
        if len(courses) > 1:
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
        cls._course_event(courses, 'offer')

    @classmethod
    def unpublish_all(cls, courses: List[Self]):
        """
        Unpublishes a list of courses.
        Args:
            courses: the list of courses to publish
        """
        cls._course_event(courses, 'claim')

    @classmethod
    def check_code(cls, value) -> Match[str] | None:
        """
        Checks if a code is valid and returns the match object if true
        Args:
            value: the course

        Returns: The match object if there's a match, else None

        """
        return re.search(Course.CODE_REGEX, value)

    @classmethod
    def _course_event(cls, courses: List[Self], event: str):
        url = f'{API_URL}/accounts/{ACCOUNT_ID}/courses'
        data = {
            'event': event,
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
    def content_url_path(self):
        return f'courses/{self.id}'

    @property
    def course_url(self) -> str:
        return self.html_content_url

    @property
    def course_code(self) -> str | None:
        """
        The course code in the form PREFIX_DEPT1234
        """
        match = self._code_match
        if not match:
            return None
        prefix = match.group(1) if match.group(1) else ""
        course_code = match.group(2) if match.group(1) else ""
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

    @property
    def is_published(self):
        return self._canvas_data['workflow_state'] == 'available'

    @property
    def syllabus(self):
        if 'syllabus_body' not in self._canvas_data:
            data = Course.get_by_id(self.id, params={
                'include[]': 'syllabus_body'
            })
            self._canvas_data['syllabus_body'] = data['syllabus_body']
        return self._canvas_data['syllabus_body']

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

    @property
    def tabs(self):
        return self.api_link.get(f'courses/{self.id}/tabs')

    @cached_property
    def front_page(self):
        try:
            return Page(self, self.api_link.get(f'{self.content_url_path}/front_page'))
        except AssertionError:
            return None

    def get_tab(self, label):
        return next(filter(lambda x: x['label'] == label, self.tabs), None)

    def set_navigation_tab_hidden(self, label: str, value: bool):
        tab = self.get_tab(label)
        if tab is None:
            return None
        return self.api_link.put(f'courses/{self.id}/tabs/{tab["id"]}', data={
            'hidden': value
        })

    def change_syllabus(self, val: str):
        self._canvas_data['syllabus_body'] = val
        self.api_link.put(f'courses/{self.id}', data={
            'course[syllabus_body]': val
        })

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
        url = f'courses/{self.id}'
        course_data = self.api_link.put(url, params={
            'offer': True
        })
        print(course_data)
        self._canvas_data = course_data
        self.reset_cache()

    def unpublish(self):
        url = f'courses/{self.id}'
        self.api_link.put(url, params={
            # WHY IS THIS CALLED CLAIM
            'course[event]': 'claim'
        })
        self._canvas_data = Course.get_by_id(self.id)._canvas_data

    def content_updates_and_fixes(self, fixes_to_run=None):
        """Summary
            updates and fixes content
        """

        self.set_navigation_tab_hidden('Dropout Detective', False)
        self.set_navigation_tab_hidden('BigBlueButton', False)

        applied_to = []
        if fixes_to_run is None:
            fixes_to_run = FIXES_TO_RUN

        for page in EvalFix.find_content(self):
            page.delete()
            applied_to.append(page)

        for fix_set in fixes_to_run:
            pages = fix_set.find_content(self)
            for page in pages:
                text = fix_set.fix(page.body)
                page.update_content(text)
                applied_to.append(page)

        syllabus = SyllabusFix.fix(self.syllabus)
        self.api_link.put(
            f'courses/{self.id}',
            data={"course[syllabus_body]": syllabus})
        self._canvas_data['syllabus_body'] = syllabus
        return applied_to

    def reset(self, prompt=True):
        """Summary
            Resets the course
        """

        # ask for confirmation if we're not running this imported from another module
        if __name__ != "__main__" or prompt and messagebox.askyesno(
                title="Do You Want To Reset",
                message=f"Are you sure you want to reset {self.course_code}?'"):
            url = f'/courses/{self.id}/reset_content'
            data = self.api_link.post(url)
            self._canvas_data['id'] = data['id']

        return False

    def import_dev_course(self, progress_bar=None, prompt=True):
        """
        Imports the dev version of a BP course into the BP course

        Args:
            prompt: whether to prompt the user before
            progress_bar: an optional progress bar to update with progress
        """
        prefix = self.code_prefix
        assert prefix.upper() == 'BP', "Course code is not a blueprint"
        dev_course = Course.get_by_code(f"DEV_{self.base_code}")

        # if we're running this right from the script (instead of a unit test) prompt to confirm
        if prompt:
            if not tk.messagebox.askyesno(
                    f"Are you sure you want to import {dev_course['name']} into {self['name']}?"):
                return None

        self.import_course(dev_course, progress_bar=progress_bar)

    def import_course(self, source_course: Self, progress_bar=None):
        """
            Copies source course into destination course. Returns the migration object
            once the migration is finished.
        Args:
            source_course: The course to copy from
            progress_bar: An optional progress bar to update

        Returns:

        """
        payload = {
            "migration_type": "course_copy_importer",
            "settings[source_course_id]": source_course["id"]}

        url = f"courses/{self.id}/content_migrations"
        response = self.api_link.post(url, data=payload)
        return poll_migration(migration=response, progress_bar=progress_bar)

    def get_parent_course(self):
        migrations = self.api_link.get(f'courses/{self.id}/content_migrations')

        # if there are no migrations return false
        if len(migrations) < 1:
            print(f"No imports found for course {self.course_code}")
            return False
        # sort by id descending so the first element is the latest created
        migrations.sort(reverse=True, key=lambda migration: migration['id'])

        try:
            for migration in migrations:
                course = Course.get_by_id(migration['settings']['source_course_id'])
                if course.code_prefix == "DEV":
                    return course

        except AssertionError:
            return Course.get_by_code('DEV_' + self.base_code)

    def get_modules(self) -> list:
        """Gets all modules including module item details
        Returns:
            list: A list of module dicts
        """
        return self.api_link.get_paged_data(
            f'courses/{self.id}/modules',
            params={
                'include[]': 'items, content_details',
            }
        )

    def get_pages(self, search_term=None) -> list[Page]:
        """Gets all pages in the course
        """
        params = {
            'include[]': 'body'
        }
        if search_term is not None:
            params['search_term'] = search_term

        return Page.get_all(self, params=params)

    def get_assignments(self, search_term=None, params=None) -> list[Assignment]:
        """Gets assignments in a course
        Args:
            search_term: Assignment names to match
            params: additional params to pass to the request

        Returns:
            a list of Assignments

        """
        params = params if params else {}
        if search_term is not None:
            params['search_term'] = search_term

        return Assignment.get_all(self, params=params)

    def get_discussions(self, search_term=None, params=None) -> list[Discussion]:
        """Gets discussions in a course
        Args:
            search_term: Assignment names to match
            params: additional params to pass to the request

        Returns:
            a list of Assignments

        """
        params = params if params else {}
        if search_term is not None:
            params['search_term'] = search_term

        return Discussion.get_all(self, params=params)

    def get_quizzes(self, search_term=None, params=None) -> list[Quiz]:
        """Gets quizzes in a course
        Args:
            search_term: Assignment names to match
            params: additional params to pass to the request

        Returns:
            a list of Assignments

        """
        params = params if params else {}
        if search_term is not None:
            params['search_term'] = search_term

        return Quiz.get_all(self, params=params)

    def get_rubrics(self) -> List['Rubric']:
        return Rubric.get_all(self)

    def get_pages_by_name(self, search_term: str) -> List[Page]:
        """Gets a page by name
        Args:
            search_term: the name of the course to search for
        """

        pages = self.get_pages(search_term)
        return pages

    def overwrite_home_page(self, profile: 'Profile') -> str:
        """Summary
            Replaces the picture and bio element, if able
            of a course home page
         Args:
            profile: The faculty profile dictionary

         Returns:
            The url of the changed page
        """
        if profile:
            new_body = format_home_page_text(profile, self)
            self.front_page.update_content(text=new_body)

        else:
            print("instructor not found for this course; skipping")

        return self.front_page.html_content_url


class User(BaseCanvasObject):
    _id_property = 'id'
    _name_property = 'name'
    _content_url_template = "users/{content_id}"
    _all_content_url_template = 'users/'

    def __init__(self, data, headers=None, api_url=None, api_link=None, account_id=None, **kwargs):
        api_link = api_link if api_link is not None else CanvasApiLink(headers, api_url, account_id)
        super().__init__(data=data, api_link=api_link, **kwargs)

    @classmethod
    def get_user_by_name(cls, name, account_id=None, params=None, **kwargs):
        if params is None:
            params = {}

        params['search_term'] = name.lower()
        link = CanvasApiLink(account_id=account_id)
        account_id = link.account_id
        data = link.get(f'accounts/{account_id}/users', params=params, **kwargs)

        return User(data=data, api_link=link, account_id=account_id)


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

    @classmethod
    def new_from_user_and_page(cls, user, page: Page):
        html = page.body
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

    @classmethod
    def get_instructor_profile_submission(cls, user):
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
            pic_path = resize_down_image(pic_path, pic_path, MAX_PROFILE_IMAGE_SIZE)
            img_upload_url = ""  # upload_image(pic_path, instructor_course_id)

        img_src = img_upload_url if img_upload_url and len(img_upload_url) > 0 else DEFAULT_PROFILE_URL

        return Profile(user=user, bio=bio, img_src=img_src, local_img_path=pic_path)


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
        course.unset_as_blueprint()
        course.reset()
        course.import_course(course, progress_bar=progress_bar)
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
            'name': 'update_and_fix_content',
            'argument': 'content',
            'message': "Do you want to content across the course"
                       + " in this (and DEV_ if you're in BP_)?",
            'func': lambda: [bp_course.content_updates_and_fixes(),
                             Course.get_by_id(get_source_course_id(bp_course.id)).content_updates_and_fixes()]
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
                status_label=status_label,
                wait_for_completion=True,
                progress_callback=lambda p, status: print(p, status))
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
        wait_for_completion: True,
        progress_bar: ttk.Progressbar = None,
        progress_callback: Callable = None,
        status_label: tk.Label = None) -> dict | None:
    """Summary
        Begins the sync process of the blueprint to its member course

    Args:
        wait_for_completion: Whether to poll the results or just let the syncs happen
        progress_callback: a callback of func(percent, status)
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
    print(migration)
    if wait_for_completion:
        poll_migration(
            migration,
            migration_url=f'{API_URL}/courses/{bp_course["id"]}/blueprint_templates/default/migrations/{migration["id"]}',
            progress_bar=progress_bar,
            progress_callback=progress_callback)


def poll_migration(
        migration: dict,
        migration_url: str | None = None,
        progress_bar: ttk.Progressbar | None = None,
        progress_callback: Callable = None,
        status_label: tk.Label | None = None,
        poll_interval: float = 2.0):
    """

    Args:
        progress_callback:
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
        if 'completed' in migration:
            if progress_bar is not None:
                update_progress_bar(progress_bar, migration['completion'])
            if progress_callback is not None:
                progress_callback(migration['completion'], status=migration['workflow_state'])
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
    modules = course.get_modules()

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
        home_page_urls.append(course.overwrite_home_page(profile))

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


def get_faculty_pages(force=False) -> list[Page]:
    """
    Gets all pages from the "faculty pages" course

    Args:
        force (bool, optional): Forces a redownload. Otherwise just returns bios file.

    Returns:
        TYPE: Description
    """
    print(force)
    faculty_course = Course.get_by_id(PROFILE_PAGES_COURSE_ID)
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

    return list(map(lambda a: Page(faculty_course, a), pages))


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


def format_home_page_text(profile: Profile, course: Course):
    """Summary
        Takes a faculty profile page, the course, and the homepage and returns
        the homepage filled in with faculty info and pic if able
    Args:
        profile: The Profile of the instructor whose bio we're inserting the front page
        course: The Course we're formatting the front page for

    Returns:
        str: html string of the front page
    """
    home_page = course.front_page

    homepage_html = home_page.body

    # Remove verification strings
    homepage_html = re.sub(r'verifier=[a-zA-Z0-9]+', '', homepage_html.strip())
    soup = BeautifulSoup(homepage_html, 'html.parser')
    h2_tags = soup.find_all('h2')
    home_page = course.front_page

    course_title = course.name

    if len(h2_tags) > 0:
        course_title = h2_tags[0].text

    # if it's cbt theme, run the new formatter
    if "cbt-banner-header" in home_page['body']:
        return format_homepage_curio(profile, home_page)
    else:
        return format_home_page_deprecated(profile, home_page, course_title)


def format_home_page_deprecated(profile, home_page, course_title):
    """
    DEPRECATED -- still here only for legacy home pages
    Args:
        profile: The profile of the instructor
        home_page: the Page pointing to the front_page of the course
        course_title: The course title to fill into the page
    Returns:
        reformatted text

    """
    with open("template.html", 'r') as f:
        template = f.read()
    text = template.format(
        course_title=course_title if course_title is not None else f' Welcome to {home_page.course.name}',
        instructor_name=profile.display_name if profile.display_name else profile.user["name"],
        img_src=profile.img_src,
        bio=profile.bio)
    text = clean_up_bio(text)
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


def format_homepage_curio(profile: Profile, homepage: Page):
    """Summary
        Formats course home pages in the curio style, rather than the old style.
    Args:
        profile: Profile information for the instructor
        homepage: Canvas api home page for the course

    Returns:
        str: The formatted homepage content with instructor pic and bio
    """
    body = homepage.body
    bio_body = profile.bio
    # change to api instead of site url
    img_data_url = re.sub('.com/', '.com/ap1/v1/', profile.img_src)
    body = re.sub(
        r'<p>\w*<span>\w*Instructor bio coming soon!\w*</span>\w*</p>',
        bio_body,
        body)

    body = re.sub(r'Meet your instructor!', rf'Meet your instructor, {profile.display_name}!', body)

    # replace image
    find_profile_image = r'src="[^"]*"([^>]*) alt="male-profile-image-placeholder.png" data-api-endpoint="[^"]*"'
    print(re.search(find_profile_image, body))
    print("img src..." + profile.img_src)
    body = re.sub(
        find_profile_image,
        f'src="{profile.img_src}"\1data-api-endpoint="{img_data_url}"',
        body)

    return body


def get_course_profile(course: Course, pages: list[Page]):
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

            instructors = get_users_by_name(name)
            if len(instructors) > 0:
                for user in instructors:
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
        profile = Profile.get_instructor_profile_submission(instructor)

    return profile


def get_users_by_name(name):
    result = requests.get(
        f"{API_URL}/accounts/self/users?search_term={name}",
        headers=HEADERS)
    return result.json()


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
    return Profile.get_instructor_profile_submission(instructor)


def get_instructor_profile(faculty_course, user) -> Profile | None:
    first_name = user["name"].split(" ")[0]
    last_name = user["name"].split(" ")[-1]
    pages = faculty_course.get_pages(user['name'])
    all_last_name_pages: list[Page] = []
    if len(pages) == 0:
        all_last_name_pages = faculty_course.get_pages(last_name)
        pages = filter(lambda page: first_name.lower() in page.name.lower(), pages)

    if len(pages) == 0:
        if len(all_last_name_pages) > 0:
            pages = all_last_name_pages
        else:
            return None

    return Profile.new_from_user_and_page(user, pages[0])


def get_instructor_profile_from_pages(
        user: dict,
        pages: list[Page],
        suppress_messages=False) -> Profile | None:
    """Summary
    Gets an instructor profile from the faculty bios pages, or any similar page objects passed in
    Args:
        suppress_messages: Suppress pop up questions; mostly for automated tests
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

    potential_page_matches = []
    iterations = 0
    for func in filter_funcs:
        potential_page_matches = list(filter(func, pages))
        if len(potential_page_matches) > 0:
            break
        iterations = iterations + 1

    page_to_use: Page | None = None

    # alert the user if there are no results
    if len(potential_page_matches) == 0:
        messagebox.showinfo(
            message=f"No profile found matching {user['name']}")
        return None

    # if we are more than two filters deep,
    # or there are more than one potential user,
    # prompt the user to confirm
    elif len(potential_page_matches) > 1 or iterations > 2:
        print(json.dumps(user, indent=2))
        print("_________________POTENTIALS______________________")
        print(json.dumps(potential_page_matches, indent=2))
        print("----------------------------------------------------")
        for potential in potential_page_matches:
            if "body" not in potential:
                continue
            if suppress_messages or messagebox.askyesno(
                    message=f"No direct match found for {user['name']}."
                            f"Do you want to use {potential['title']}?"):
                page_to_use = potential
                break

    # otherwise pick the first result
    else:
        page_to_use = potential_page_matches[0]

    return Profile.new_from_user_and_page(user, page_to_use)


def resize_down_image(in_path, max_width, out_path=None, img_format=None):
    """Summary
    Resizes an image to a maximum width

    Args:
        img_format: File format if relevant. Defaults to None.
        max_width: the maximum width to scale down to
        in_path: Path to the original image
        out_path: Path to save the output image, if different


    Returns:
        The path to the resized image on disk
    """
    if out_path is None:
        out_path = in_path

    with Image.open(in_path) as img:
        if max_width >= img.size[0]:
            img.save(out_path)
            return in_path

        # Calculate the new height to preserve the aspect ratio
        width_percent = (max_width / float(img.size[0]))
        new_height = int((float(img.size[1]) * float(width_percent)))

        # Resize the image using the appropriate resampling filter
        resized_img = img.resize(
            (max_width, new_height), Image.Resampling.BILINEAR)

        # Save the resized image
        resized_img.save(out_path, img_format)

    return out_path


def get_instructor_page(user: dict | str) -> list[Page]:
    """Gets the page in Faculty Bios course that matches this instructor

    Args:
        user(dict | str): A dictionary containing the json user response from canvas or the instructor's name as a str

    Returns:
        list: A list of all matches
    """
    search_string = user if type(user) is str else user['name']

    url = f"{API_URL}/courses/{PROFILE_PAGES_COURSE_ID}/pages" \
          + f"?per_page=999&search_term={urllib.parse.quote(search_string)}"
    course = Course.get_by_id(PROFILE_PAGES_COURSE_ID)
    pages = course.get_pages_by_name(search_string)
    for page in pages:
        print(page.name)
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
