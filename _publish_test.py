
import unittest
from typing import List

import publish_script
from publish_script import Term, Course, SyllabusFix, EvalFix, Page
import requests

CONSTANTS_FILE = 'constants_test.json'

CONSTANTS = publish_script.load_constants(CONSTANTS_FILE, publish_script)


accounts = requests.get(f'{publish_script.API_URL}/accounts', headers=publish_script.HEADERS).json()

API_URL = publish_script.API_URL
ACCOUNT_ID = publish_script.ACCOUNT_ID
ROOT_ACCOUNT_ID = publish_script.ROOT_ACCOUNT_ID
TEST_COURSE_CODE: str = 'TEST000'
TEST_TERM_CODE = 'DE/HL-24-Jan'

print(publish_script.API_URL)
assert('test' in publish_script.API_URL)


def get_test_course():
    return Course.get_by_code(f'BP_{TEST_COURSE_CODE}')


def get_test_section():
    return Course.get_by_code(f'24-Jan_{TEST_COURSE_CODE}')


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
        course = Course.get_by_code('DEV_' + TEST_COURSE_CODE)
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



class TestCourseResetAndImport(unittest.TestCase):
    """
    Tests for getting course reset and importing
    Can take a long time to run
    """
    def test_reset(self):
        course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")

        original_course_data = course._canvas_data
        original_course_id = course['id']
        course.unset_as_blueprint()
        course.reset()
        self.assertNotEqual(original_course_id, course.id, "Course id has not been changed on reset")

        course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}')
        self.assertIsNotNone(course, "Course does not exist")
        self.assertFalse(publish_script.get_modules(int(course['id'])), "Course contains modules after reset")

    def test_import_dev(self):
        self.maxDiff = None
        bp_course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}')
        bp_course.import_dev_course(prompt=False)
        bp_course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}', params={'include[]': 'syllabus_body'})
        dev_course = Course.get_by_code(f'DEV_{TEST_COURSE_CODE}', params={'include[]': 'syllabus_body'})
        self.assertEqual(
            len(bp_course['syllabus_body']), len(dev_course['syllabus_body']), "Course syllabi do not mach")

        bp_modules = publish_script.get_modules(int(bp_course.id))
        dev_modules = publish_script.get_modules(int(bp_course.id))
        self.assertEqual(
            get_item_names(flatten_modules(bp_modules)),
            get_item_names(flatten_modules(dev_modules)),
            f"BP modules do not match dev modules.")


class TestProfilePages(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_download_faculty_pages(self):
        bios = publish_script.get_faculty_pages(True)
        self.assertGreater(len(bios), 10, "No Bios Found")
        self.assertListEqual(bios, publish_script.get_faculty_pages(), msg="Bios not returning properly")

    def test_get_instructor_page(self):
        section = get_test_section()
        user = publish_script.get_canvas_instructor(section['id'])
        pages = publish_script.get_instructor_page(user)
        pages_from_name = publish_script.get_instructor_page(user['name'])
        self.assertEqual(len(pages), 1, msg="Returned more than one instructor page")
        self.assertListEqual(pages, pages_from_name, msg="Returned different pages for instructor pages")

    def test_get_course_profile(self):
        section = get_test_section()
        pages = publish_script.get_faculty_pages()
        profile = publish_script.get_course_profile(section, pages)
        user = publish_script.get_canvas_instructor(section['id'])
        self.assertEqual(profile.user['name'], user['name'], msg="Profile names do not match")

    def test_change_front_page(self):
        course = get_test_course()
        instructors = publish_script.get_users_by_name('Test Testersson')
        self.assertEqual(len(instructors), 1, msg="Returned more than one")
        instructor = instructors[0]
        pages = publish_script.get_instructor_page(instructor)
        profile = publish_script.get_instructor_profile_from_pages(instructor, pages)


class TestCourse(unittest.TestCase):

    original_syllabus: str = None

    def setUp(self):
        course = get_test_course()
        self.original_syllabus = course.syllabus
        modules = publish_script.get_modules(course['id'])
        if len(modules) == 0:
            course.import_dev_course(course, prompt=False)

    def tearDown(self):
        course = get_test_course()
        course.change_syllabus(self.original_syllabus)

    def test_course_properties(self):
        code = f"BP_{TEST_COURSE_CODE}"
        course: Course = Course.get_by_code(code)
        self.assertEqual(course['name'], course._canvas_data['name'], "course['name'] does not match its data")

    def test_get_course(self):
        code = f"BP_{TEST_COURSE_CODE}"
        course: Course = Course.get_by_code(code)
        course_by_id: Course = Course.get_by_id(course.id)
        # The test course code is a stub; we should be able to get all the prefix matching versions:
        # BP, DEV, and any Sections
        courses: List[Course] = Course.get_all_by_code(TEST_COURSE_CODE)
        self.assertIsNotNone(course)
        self.assertEqual(course.course_code, code, "course codes by id and code do not match")
        self.assertEqual(course_by_id.id, course.id, "ids of course by id and by code do not match")
        self.assertEqual(course_by_id['name'], course['name'], "names of course by id and by code do not match")
        self.assertGreater(len(courses), 2, "Not enough courses found")

    def test_unset_blueprint(self):
        course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        course.unset_as_blueprint()
        self.assertFalse(course.is_blueprint, "Course is a blueprint")

    def test_set_blueprint(self):
        course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}')
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        course.set_as_blueprint()
        self.assertTrue(course.is_blueprint, "Course is not blueprint")
        print(course['blueprint_restrictions'])
        self.assertEqual(
            course['blueprint_restrictions'],
            {
                'content': True,
                'points': True,
                'due_dates': True,
                'availability_dates': True,
            },
            "Restrictions not properly set on course")

    def test_get_courses_by_term(self):
        term = Term.get_by_code(TEST_TERM_CODE)
        courses_by_term = Course.get_all_by_code(TEST_COURSE_CODE, term=term)
        courses_by_term_name = Course.get_all_by_code(f'{term.code}_{TEST_COURSE_CODE}')
        self.assertIsNotNone(courses_by_term_name, f"Courses not found")
        self.assertGreaterEqual(len(courses_by_term), 3, f"There are {len(courses_by_term)}")
        self.assertListEqual(
            courses_by_term,
            courses_by_term_name,
            "courses searched by term and by term name do not match")

    def test_find_sections(self):
        term = Term.get_by_code(TEST_TERM_CODE)
        course = Course.get_by_code(f'BP_{TEST_COURSE_CODE}')
        self.assertIsNotNone(term, f"Term not found for code{TEST_TERM_CODE}")
        potential_sections = course.get_potential_sections(term)
        courses_by_term_name = Course.get_all_by_code(f'{term.code}_{course.base_code}')
        self.assertListEqual(
            potential_sections, courses_by_term_name,
            f"Potential sections not returning matching sections")

    def test_syllabus_fix(self):
        with open('syllabus_template.html', 'r') as f:
            syllabus_template = f.read()
        course = get_test_course()

        original_syllabus = course.syllabus
        new_syllabus = SyllabusFix.fix(original_syllabus)
        self.maxDiff = None
        course.content_updates_and_fixes()
        self.assertEqual(course.syllabus, new_syllabus)
        self.assertEqual(len(new_syllabus), len(course.syllabus))

    async def test_lock(self):
        course = get_test_course()
        course.set_as_blueprint()
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        self.assertTrue(await publish_script.lock_module_items_async(course), "locking did not succeed")

    def test_lock_sync(self):
        course = get_test_course()
        course.set_as_blueprint()
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        self.assertTrue(publish_script.lock_module_items(course), "locking did not succeed")

    def test_course_publish(self):
        course = get_test_course()
        course.unpublish()
        self.assertFalse(course.is_published)
        course.publish()
        self.assertTrue(course.is_published)

    def test_tabs(self):
        course = get_test_course()
        tabs = course.tabs
        self.assertGreater(len(tabs), 0, "No tabs found")
        tab = course.get_tab('Dropout Detective')
        self.assertIsNotNone(tab, "Dropout Detective not found")
        course.tab_hidden('Dropout Detective', False)
        tab = course.get_tab('Dropout Detective')
        if 'hidden' in tab:
            self.assertFalse(tab['hidden'], "Dropout Detective not hidden")
        course.tab_hidden('Dropout Detective', True)
        tab = course.get_tab('Dropout Detective')
        self.assertTrue(tab['hidden'], "Dropout Detective hidden")


class TestContent(unittest.TestCase):
    test_page_content = "<div>TEST</div>"

    def test_edit_and_revert_page(self):
        course = get_test_course()
        pages = course.get_pages_by_name("Course Evaluation")
        for page in pages:
            body = page.body
            original_body = body
            revisions = page.revisions
            revisions.sort(key=lambda revision: revision['revision_id'], reverse=True)
            revert_id = revisions[0]['revision_id']
            page.update_content(self.test_page_content)
            page = Page.get_by_id(course, page.id)
            self.assertEqual(page.body, self.test_page_content)
            page.reset_content(revert_id)
            page = Page.get_by_id(course, page.id)
            self.assertEqual(page.body, original_body)

    def test_fix(self, fix):
        course = get_test_course()
        pages = fix.find_content(course)
        for page in pages:
            backup = page.body
            text = fix.fix(page.body)
            page.update_content(text)
            reclaim_page = Page.get_by_id(course, page.id)
            self.assertEqual(reclaim_page.body, text)
            page.revert_last_changeset()
            self.assertEqual(page.body, backup)

    def test_eval_fix(self):
        self.test_fix(EvalFix)

    def test_resource_fix(self):
        self.test_fix(publish_script.ResourcesFixSet)

    def test_overview_fix(self):
        self.test_fix(publish_script.OverviewFixSet)

    def test_front_page_fix(self):
        self.test_fix(publish_script.FrontPageFixSet)


class TestTerm(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self) -> None:
        pass

    def test_load_by_code(self):
        term = Term.get_by_code(TEST_TERM_CODE)
        self.assertIsNotNone(term, "Term not found for code{}".format(TEST_TERM_CODE))
        self.assertEqual(term['name'], TEST_TERM_CODE, "Term code doesn't match")


class TestPublish(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass



