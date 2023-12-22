import unittest

from publish_script import *

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

bp_test_course_code: str = 'TEST000'

print(api_url)


class TestCourseResetAndImport(unittest.TestCase):
    def test_reset(self):
        course = get_course_by_code(f'BP_{bp_test_course_code}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")

        original_course_id = course['id']
        reply_course = reset_course(course)
        self.assertNotEqual(original_course_id, reply_course['id'], "Course id has not been changed on reset")

        course = get_course_by_code(f'BP_{bp_test_course_code}')
        self.assertIsNotNone(course, "Course does not exist")
        self.assertFalse(get_modules(int(course['id'])), "Course contains modules after reset")

        self.assertEqual(reply_course, course, f"Reset course is not the same as searched for course - {reply_course['id']}, {course['id']}")

    def test_import_dev(self):
        course = get_course_by_code(f'BP_{bp_test_course_code}')

