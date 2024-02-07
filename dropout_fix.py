import publish_script as ps
from publish_script import Course
from tkinter import simpledialog, messagebox
ps.load_constants('constants.json')

course_string = simpledialog.askstring(
    "Course Codes for Dropdown Detective",
    "Add a list of course BP names to modify\n" +
    "Separate ids by space\n" +
    "e.g. BP_ANIM101 BP_ANIM102 BP_ANIM103 BP_ANIM104")

not_found = []


def progress(percent, status, **args):
    print(percent, status)


i = 0

for code in course_string.split():
    print(f"Starting for {code}")
    if '_' not in code:
        code = 'BP_' + code
    course = Course.get_by_code(code)
    if not course:
        not_found.append(code)
        continue
    i = i + 1

    courses = [course]
    parent = course.get_parent_course()
    if parent and 'BP' in course.code_prefix:
        courses.append(parent)

    for update_course in courses:
        tab = update_course.set_navigation_tab_hidden('Dropout Detective', False)
        ps.open_browser_func([f'{update_course.course_url}/settings#tab-navigation'])

    if course.associated_courses:
        print(map(lambda c: c.code, course.associated_courses))
        ps.begin_course_sync(bp_course=course, progress_callback=progress, wait_for_completion=True)
        for associate_course in course.associated_courses:
            ps.open_browser_func([f'{associate_course.course_url}/settings#tab-navigation'])


messagebox.showinfo("Finished", f"Finished! \n{i} BP/DEV pairs found and updated.")



