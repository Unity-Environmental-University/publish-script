import json
import csv

import publish_script
from publish_script import Course, Term, Rubric, RubricAssociation

publish_script.load_constants('../constants_test.json')


def main():
    check_all_courses()


def check_all_courses():
    term = Term.get_by_code('DE8W01.08.24')
    courses = Course.get_all_by_code(code=None, term=term)
    codes = [course.base_code for course in courses]
    codes = list(set(codes))
    bps = Course.get_all_by_code('BP_')

    courses = [bp for bp in bps if bp.base_code in codes]
    print([course.base_code for course in courses])

    results = []
    passed = []
    for course in courses:
        rubrics: list[Rubric] = course.get_rubrics()
        course_failed = False
        for rubric in rubrics:
            associations: list[RubricAssociation] = [ a for a in rubric.associations if a["purpose"] == "grading" ]
            for association in associations:
                print(association._canvas_data)
                if not association["use_for_grading"]:
                    print("FAIL")
                    results.append((course.course_code, rubric.name))
                else:
                    print("PASS")

    json.dump(results, open('../dump.json', 'w'))
    print(results)


if __name__ == '__main__':
    main()