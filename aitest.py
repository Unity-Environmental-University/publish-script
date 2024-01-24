import random

from openai import OpenAI
import json

import publish_script
from publish_script import Course, Page

publish_script.load_constants('constants.json')
constants = json.load(open('constants.json'))
OPENAI_API_KEY = constants['openApiKey']
client = OpenAI(
  api_key=OPENAI_API_KEY
)

# response = client.chat.completions.create(
#   model="gpt-3.5-turbo",
#   messages=[
#     {"role": "system", "content": "You are a helpful assistant."},
#     {"role": "user", "content": "Who won the world series in 2020?"},
#     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
#     {"role": "user", "content": "Where was it played?"}
#   ]
# )


courses = Course.get_all_by_code('DEV_')
out = []
courses = random.choices(courses, k=200)

for i, course in enumerate(courses):
    project_pages = course.get_pages_by_name('project')
    overview_pages = course.get_pages_by_name('course overview')
    print(f'%{i/len(courses) * 100}')
    project_text = project_pages[0].body if len(project_pages) > 0 else None
    overview_text = overview_pages[0].body if len(overview_pages) > 0 else None
    print(course.course_code)
    out.append({
      'course': course.course_code,
      'project': project_text,
      'overview': overview_text
    })

json.dump(out, fp=open('course_data/projects.json', 'w'))