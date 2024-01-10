import publish_script as ps
from publish_script import Course
from tkinter import simpledialog

course_string = simpledialog.askstring(
    "Add a list of course BP names to edit\n" +
    "Separate ids by space\n" +
    "e.g. BP_ANIM101 BP_ANIM102 BP_ANIM103 BP_ANIM104")

not_found = []
for code in course_string.split():
    course = Course.get_by_code(code)
    if not course:
        not_found.append(code)
        continue





