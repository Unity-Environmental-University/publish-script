import functools
import unittest
import publish_script
import re
import requests
import json
from functools import reduce
CONSTANTS_FILE = 'constants_test.json'
with open(CONSTANTS_FILE) as f:
    constants = json.load(f)

publish_script.api_token = constants["apiToken"]
publish_script.api_url = constants["apiUrl"]
publish_script.html_url = re.sub('/api/v1', '', constants["apiUrl"])

instructor_course_id = constants["instructorCourseId"]
profile_assignment_id = constants["profileAssignmentId"]
profile_pages_course_id = constants["profilePagesCourseId"]

default_profile_url = f"{publish_script.html_url}/users/9230846/files/156109264/preview"
publish_script.live_url = constants["liveUrl"]

# Authorize the request.
publish_script.headers = {"Authorization": f"Bearer {publish_script.api_token}"}
publish_script.live_headers = {"Authorization": f'Bearer {constants["liveApiToken"]}'}

accounts = requests.get(f'{publish_script.api_url}/accounts', headers=publish_script.headers).json()
account_ids = dict()
for account in accounts:
    account_ids[account['name']] = account['id']

ACCOUNT_ID = account_ids['Distance Education']
ROOT_ACCOUNT_ID = account_ids['Unity College']

test_course_code: str = 'TEST000'

print(publish_script.api_url)
assert('test' in publish_script.api_url)


def get_item_names(items):
    # also work for modules
    if 'items' in items:
        items = items['items']
    return list(map(lambda a: a['name'] if 'name' in a else a['title'], items))


def flatten_modules(modules: list):
    out = []
    return [item for module in modules for item in module['items']]


class TestMisc(unittest.TestCase):
    def test_flatten_module(self):
        course = publish_script.get_course_by_code('DEV_' + test_course_code)
        modules = publish_script.get_modules(course['id'])
        flattened_modules = flatten_modules(modules)
        print(flattened_modules)
        alt_flattened_modules = []
        for module in modules:
            alt_flattened_modules = alt_flattened_modules + module['items']
        flat_module_size = len(flattened_modules)

        print(get_item_names(alt_flattened_modules))
        self.assertEqual(
            len(flattened_modules), len(alt_flattened_modules),
            f'Not the right size: {flat_module_size} items across modules')
        self.assertEqual(
            ','.join(get_item_names(flattened_modules)),
            ','.join(get_item_names(alt_flattened_modules)),
            f'flattened_modules={flattened_modules}')


class TestContentFixes(unittest.TestCase):
    def test_fix_intro_header(self):
        course = publish_script.get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")


class TestCourseResetAndImport(unittest.TestCase):
    def test_reset(self):
        course = publish_script.get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")

        original_course_id = course['id']
        reply_course = publish_script.reset_course(course)
        self.assertNotEqual(original_course_id, reply_course['id'], "Course id has not been changed on reset")

        course = publish_script.get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Course does not exist")
        self.assertFalse(publish_script.get_modules(int(course['id'])), "Course contains modules after reset")

        self.assertEqual(reply_course, course, f"Reset course is not the same as searched for course - {reply_course['id']}, {course['id']}")

    def test_import_dev(self):
        self.maxDiff = None
        bp_course = publish_script.get_course_by_code(f'BP_{test_course_code}')
        publish_script.import_dev_course(bp_course)
        bp_course = publish_script.get_course_by_code(f'BP_{test_course_code}', params={'include[]': 'syllabus_body'})
        dev_course = publish_script.get_course_by_code(f'DEV_{test_course_code}', params={'include[]': 'syllabus_body'})
        self.assertEqual(
            len(bp_course['syllabus_body']), len(dev_course['syllabus_body']), "Course syllabi do not mach")

        bp_modules = publish_script.get_modules(int(bp_course['id']))
        dev_modules = publish_script.get_modules(int(bp_course['id']))
        self.assertEqual(
            get_item_names(flatten_modules(bp_modules)),
            get_item_names(flatten_modules(dev_modules)),
            f"BP modules do not match dev modules.")

    def test_unset_blueprint(self):
        course = publish_script.get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        response_course = publish_script.unset_course_as_blueprint(course)
        self.assertFalse(response_course['blueprint'], "Course isn't a blueprint")

    def test_set_blueprint(self):
        course = publish_script.get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        response_course = publish_script.set_course_as_blueprint(course)
        print(response_course['blueprint_restrictions'])
        self.assertEqual(
            response_course['blueprint_restrictions'],
            {
                'content': True,
                'points': True,
                'due_dates': True,
                'availability_dates': True,
            },
            "Restrictions not properly set on course")


