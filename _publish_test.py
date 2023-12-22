import functools
import unittest
from publish_script import *
from functools import reduce
CONSTANTS_FILE = 'constants_test.json'
with open(CONSTANTS_FILE) as f:
    constants = json.load(f)

api_token = constants["apiToken"]
api_url = constants["apiUrl"]
html_url = re.sub('/api/v1', '', constants["apiUrl"])

instructor_course_id = constants["instructorCourseId"]
profile_assignment_id = constants["profileAssignmentId"]
profile_pages_course_id = constants["profilePagesCourseId"]

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

test_course_code: str = 'TEST000'

print(api_url)
assert('test' in api_url)


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
        course = get_course_by_code('DEV_' + test_course_code)
        modules = get_modules(course['id'])
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


class TestCourseResetAndImport(unittest.TestCase):
    def test_reset(self):
        course = get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")

        original_course_id = course['id']
        reply_course = reset_course(course)
        self.assertNotEqual(original_course_id, reply_course['id'], "Course id has not been changed on reset")

        course = get_course_by_code(f'BP_{test_course_code}')
        self.assertIsNotNone(course, "Course does not exist")
        self.assertFalse(get_modules(int(course['id'])), "Course contains modules after reset")

        self.assertEqual(reply_course, course, f"Reset course is not the same as searched for course - {reply_course['id']}, {course['id']}")

    def test_import_dev(self):
        self.maxDiff = None
        bp_course = get_course_by_code(f'BP_{test_course_code}')
        import_dev_course(bp_course)
        bp_course = get_course_by_code(f'BP_{test_course_code}', params={'include[]': 'syllabus_body'})
        dev_course = get_course_by_code(f'DEV_{test_course_code}', params={'include[]': 'syllabus_body'})
        self.assertEqual(
            len(bp_course['syllabus_body']), len(dev_course['syllabus_body']), "Course syllabi do not mach")

        bp_modules = get_modules(int(bp_course['id']))
        dev_modules = get_modules(int(bp_course['id']))
        self.assertEqual(
            get_item_names(flatten_modules(bp_modules)),
            get_item_names(flatten_modules(dev_modules)),
            f"BP modules do not match dev modules.")