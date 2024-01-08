
import unittest
import publish_script

import requests

CONSTANTS_FILE = 'constants_test.json'

CONSTANTS = publish_script.load_constants(CONSTANTS_FILE, publish_script)

accounts = requests.get(f'{publish_script.API_URL}/accounts', headers=publish_script.HEADERS).json()

API_URL = publish_script.API_URL
ACCOUNT_ID = publish_script.ACCOUNT_ID
ROOT_ACCOUNT_ID = publish_script.ROOT_ACCOUNT_ID
test_course_code: str = 'TEST000'

print(publish_script.API_URL)
assert('test' in publish_script.API_URL)


def get_test_course():
    return publish_script.get_course_by_code(f'BP_{test_course_code}')


def get_test_section():
    return publish_script.get_course_by_code(f'24-Jan_{test_course_code}')


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


class TestLocking(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        course = get_test_course()
        modules = publish_script.get_modules(course['id'])
        if len(modules) == 0:
            publish_script.import_dev_course(course)

    async def test_lock(self):
        course = get_test_course()
        publish_script.set_course_as_blueprint(course)
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        self.assertTrue(await publish_script.lock_module_items_async(course), "locking did not succeed")

    def test_lock_sync(self):
        course = get_test_course()
        publish_script.set_course_as_blueprint(course)
        self.assertIsNotNone(course, "Can't Find Test Course by code")
        self.assertTrue(publish_script.lock_module_items(course), "locking did not succeed")

