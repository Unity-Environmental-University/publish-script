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

bp_test_course_code: str = 'UNITTEST'

print(api_url)


class TestCourseReset(unittest.TestCase):
    def runTest(self):
        course = get_course_by_code(f'BP_{bp_test_course_code}')
        reset_course(course)
        course = get_course_by_code(f'BP_{bp_test_course_code}')
        self.assertTrue(course is not None, "Course does not exist")
        self.assertIn("id", course.keys(), "Course does not contain id")
        self.assertFalse(get_modules(int(course['id'])), "Course does not contain modules")
