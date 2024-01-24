import webbrowser
import re

from fixes import resources_page
import publish_script as ps
from publish_script import Course, EvalFix, Page
from tkinter import simpledialog, messagebox
import tkinter as tk


not_found = []

fixes_to_run = [
    # EvalFix,
    resources_page.Fixes
]

def progress(percent, status, **args):
    print(percent, status)


def make_default_bp(code_set):
    for code in code_set:
        if '_' not in code:
            code_set.remove(code)
            code_set.add('BP_' + code)

def main():
    ps.load_constants('constants_test.json')
    window = tk.Tk()
    clipboard = window.clipboard_get()
    codes: list[str] = []
    if clipboard:
        code_string_list = clipboard.split('\n')
        for item in code_string_list:
            maybe_code = re.sub('\t','', item)
            if Course.check_code(maybe_code) and ' ' not in maybe_code:
                codes.append(maybe_code)

    unique_codes = set(codes)
    open_course_queue: list = []
    make_default_bp(unique_codes)
    while len(unique_codes) == 0 or not messagebox.askyesno('Use These Codes', "Use Codes?:\n" + ", ".join(unique_codes)):
        course_string = simpledialog.askstring(
            "Course Codes",
            "Add a list of course BP names to edit\n" +
            "Separate ids by space\n" +
            "e.g. BP_ANIM101 BP_ANIM102 BP_ANIM103 BP_ANIM104")

        # If the user cancels out, exit program
        if course_string is None:
            return

        codes = course_string.split()
        unique_codes = set(codes)

        make_default_bp(unique_codes)

    applied_to = []
    for code in unique_codes:
        print(f"Starting for {code}")
        course = Course.get_by_code(code)
        if not course:
            not_found.append(code)
            continue

        courses = [course]
        parent = course.get_parent_course()
        if parent and 'BP' in course.code_prefix:
            courses.append(parent)

        for update_course in courses:
            for fix_set in fixes_to_run:

                pages = fix_set.find_content(update_course)
                for page in pages:
                    text = fix_set.fix(page.body)
                    page.update_content(text)
                    webbrowser.open_new_tab(page.html_content_url)
                applied_to.append(course)

        if course.associated_courses:
            print(map(lambda c: c.code, course.associated_courses))
            wait = False
            ps.begin_course_sync(bp_course=course, progress_callback=progress, wait_for_completion=wait)
            for associate_course in course.associated_courses:
                if wait:
                    ps.open_browser_func([f'{associate_course.course_url}/pages/course-evaluation'])
                else:
                    open_course_queue.append(associate_course)

    messagebox.showinfo("Finished", f"Finished! \n{len(applied_to)} Devs or BPs were affected\n" +
                        f'{", ".join([a.course_code for a in applied_to])}')

    for course in open_course_queue:
        ps.open_browser_func([f'{course.course_url}/pages/course-evaluation'])


if __name__ == "__main__":
    main()
