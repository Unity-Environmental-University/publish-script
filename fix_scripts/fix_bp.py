import webbrowser
import re

import publish_script as ps
from publish_script import Course, EvalFix
from tkinter import simpledialog, messagebox
import tkinter as tk


not_found = []

fixes_to_run = []

open_as_we_go: bool = False


def progress(percent, status, **args):
    print(percent, status)


def make_default_bp(code_set):
    for code in code_set:
        if '_' not in code:
            code_set.remove(code)
            code_set.add('BP_' + code)


def main():
    ps.load_constants('../constants.json')
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
    open_page_queue: list = []
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
    for i, code in enumerate(unique_codes):
        print(f"Starting for {code}")
        percent_done = i / len(unique_codes) * 100
        print("Progress: %", percent_done)
        course = Course.get_by_code(code)
        if not course:
            not_found.append(code)
            continue

        courses = [course]
        parent = course.get_parent_course()
        if parent and 'BP' in course.code_prefix:
            courses.append(parent)

        applied_to = []
        for update_course in courses:
            for page in EvalFix.find_content(update_course):
                page.delete()
                applied_to.append(update_course)

            for fix_set in fixes_to_run:
                applied_to += update_course.content_updates_and_fixes([fix_set])

        if course.associated_courses:
            print(map(lambda c: c.code, course.associated_courses))
            wait = False
            ps.begin_course_sync(bp_course=course, progress_callback=progress, wait_for_completion=wait)

    messagebox.showinfo("Finished", f"Finished! \n{len(applied_to)} Devs or BPs were affected\n" +
                        f'{", ".join([a.course_code for a in applied_to])}')

    for page in applied_to:
        webbrowser.open(page.html_content_url, new=2, autoraise=False)


if __name__ == "__main__":
    main()
# ANIM315 BIOL203 BIOL103