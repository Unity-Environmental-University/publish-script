
import unittest
import publish_script
from publish_script import Course, Term, Rubric, RubricAssociation
import requests
import json
import csv

CONSTANTS_FILE = 'constants.json'
with open(CONSTANTS_FILE) as f:
    constants = json.load(f)

publish_script.load_constants(CONSTANTS_FILE)

instructor_course_id = constants["instructorCourseId"]
profile_assignment_id = constants["profileAssignmentId"]
profile_pages_course_id = constants["profilePagesCourseId"]

default_profile_url = f"{publish_script.HTML_URL}/users/9230846/files/156109264/preview"
publish_script.LIVE_URL = constants["liveUrl"]

# Authorize the request.

accounts = requests.get(f'{publish_script.API_URL}/accounts', headers=publish_script.HEADERS).json()
account_ids = dict()
for account in accounts:
    account_ids[account['name']] = account['id']

ACCOUNT_ID = account_ids['Distance Education']
ROOT_ACCOUNT_ID = account_ids['Unity College']
API_URL = publish_script.API_URL
test_course_code: str = 'TEST000'

print(publish_script.API_URL)


class TestOneOff(unittest.TestCase):
    def test_comm101(self):
        section = Course.get_by_code('24-Jan_COMM101-03')
        user = publish_script.get_canvas_instructor(section['id'])

        pages = publish_script.get_instructor_page(user)
        pages_from_name = publish_script.get_instructor_page(user['name'])
        self.assertEqual(len(pages), 1, msg="Returned more than one instructor page")
        self.assertListEqual(pages, pages_from_name, msg="Returned different pages for instructor pages")

    def test_rubrics(self):
        # course_codes = ['DEV_ARTS101', 'DEV_MATH201']
        # courses = [Course.get_by_code(code) for code in course_codes]
        term = Term.get_by_code('24-Jan')
        courses = Course.get_all_by_code(code=None, term=term)
        codes = [course.base_code for course in courses]
        codes = list(set(codes))
        bps = Course.get_all_by_code('BP_')

        courses = [bp for bp in bps if bp.base_code in codes]

        results = []
        passed = []
        for course in courses:
            rubrics: list[Rubric] = course.get_rubrics()
            course_failed = False
            for rubric in rubrics:
                associations: list[RubricAssociation] = rubric.associations
                for association in associations:
                    if not association.use_for_grading:
                        results.append(course)
                        print(course.course_code, rubric)
                        course_failed = True
                        continue
                    else:
                        passed.append(rubric)
            if course_failed:
                continue

        out_list = [course.course_code for course in results]
        print(out_list)
        self.assertGreater(len(results), 0, '\n'.join([a["course"].base_code for a in results]))


class TestSectionInserted(unittest.TestCase):
    def test_get_terms(self):
        url = f'{publish_script.API_URL}/accounts/{publish_script.ROOT_ACCOUNT_ID}/terms'
        terms = requests.get(url, headers=publish_script.HEADERS).json()
        print(json.dumps(terms, indent=2))

    def test_get_course(self):
        course = Course.get_by_code('23-Nov_ANIM401')
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
            courses = Course.get_by_code(code, return_list=True)

            for course in courses:
                print(course)
                instructor = publish_script.get_canvas_instructor(course['id'])
                if instructor['name'] in names_by_code[code]:
                    self.assertTrue(self.is_section_setup(course))

    @staticmethod
    def is_section_setup(course):
        sections = course.get_sections()
        grading_sections = list(filter(lambda a: a['name'].lower() == 'grading', sections))
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
                f'{API_URL}/sections/{section["id"]}/enrollments',
                headers=publish_script.HEADERS).json()
            assert len(enrollments) == 1
            enrollment = enrollments[0]
            print(enrollment)
            assert enrollment['user']['name'] == instructor['name']
            return True
        return False




if __name__ == '__main__':
    unittest.main()
