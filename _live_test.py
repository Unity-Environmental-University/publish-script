import csv
import functools
import unittest
import publish_script
import re
import requests
import json
import csv
from functools import reduce
CONSTANTS_FILE = 'constants.json'
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
api_url = publish_script.api_url
test_course_code: str = 'TEST000'

print(publish_script.api_url)


def is_section_setup(course):
    sections = publish_script.get_sections(course)
    grading_sections = list( filter(lambda section: section['name'].lower() == 'grading', sections))
    if len(grading_sections) > 0:
        instructor = publish_script.get_canvas_instructor(course['id'])
        print(course['name'])
        print(instructor['name'])
        print(grading_sections)
        section = grading_sections[0]
        assert section['start_at'] == '2023-12-28T05:00:00Z' or section['start_at'] == '2023-12-27T05:00:00Z'
        assert section['end_at'] == '2023-12-31T05:00:00Z' or section['end_at'] == '2024-01-01T05:00:00Z'
        assert section['restrict_enrollments_to_section_dates']
        enrollments = requests.get(
            f'{api_url}/sections/{section["id"]}/enrollments',
            headers=publish_script.headers).json()
        assert len(enrollments) == 1
        enrollment = enrollments[0]
        print(enrollment)
        assert enrollment['user']['name'] == instructor['name']
        return True
    return False


class TestInsertSection(unittest.TestCase):
    def test_get_terms(self):
        url = f'{publish_script.api_url}/accounts/{publish_script.ROOT_ACCOUNT_ID}/terms'
        terms = requests.get(url, headers=publish_script.headers).json()
        print(json.dumps(terms, indent=2))

    def test_get_course(self):
        course = publish_script.get_course_by_code('23-Nov_ANIM401')
        print(course)
        self.assertTrue(course)

    def test_section_set(self):
        with open("enrollments.csv") as csvfile:
            reader = csv.DictReader(csvfile,['dept', 'code', 'source', 'instructor', 'assigned', 'done', 'skip'])
            names_by_code = {}
            for row in reader:
                print(row)
                if row['skip'] == 'X':
                    continue
                names = []
                code = f"23-Nov_{row['dept']}{row['code']}"
                if code in names_by_code:
                    names = names_by_code[code]
                else:
                    names = names_by_code[code] = names

                instructor_name = row['instructor']
                if instructor_name not in names:
                    names.append(instructor_name)

        for code in names_by_code.keys():
            print(code)
            courses = publish_script.get_course_by_code(code, return_list=True)

            for course in courses:
                print(course)
                instructor = publish_script.get_canvas_instructor(course['id'])
                if instructor['name'] in names_by_code[code]:
                    self.assertTrue(is_section_setup(course))

if __name__ == '__main__':
    unittest.main()
