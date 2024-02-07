import sys
import requests
import urllib.parse
import os
import PyPDF2
import json
import datetime
import tkinter as tk
from tkinter import simpledialog
import publish_script
from tkinter import ttk
from publish_script import Quiz, Course
CONSTANTS_FILE = 'constants.json'

# Open the file and read the contents
with open(CONSTANTS_FILE, 'r') as f:
    constants = json.load(f)

# save the api key
api_token = constants["apiToken"]
API_URL = constants["apiUrl"]


# Authorize the request.
headers = {"Authorization": f"Bearer {api_token}" }

publish_script.load_constants(CONSTANTS_FILE)

def main():
    course_id: int
    offset: int
    if len(sys.argv) > 1:
        course_id = int(sys.argv[1])
    else:
        course_id = tk.simpledialog.askinteger(
            "What Course?",
            "Enter the course_id of the course" +
            "(cut the number out of the url and paste here)")

    if len(sys.argv) > 2:
        offset = int(sys.argv[2])
    else:
        offset = tk.simpledialog.askinteger("How Many Days", "Enter the number of days to offset all assignment dates")

    course = Course.get_by_id(course_id)

    assignments = publish_script.get_paged_data(f"{API_URL}/courses/{course_id}/assignments?include=due_at")
    quizzes = Quiz.get_all(course)
    for quiz in quizzes:
        quiz.due_at_timedelta(days=offset)

    for assignment in assignments:
        print(assignment["due_at"])

        # If we don't have a due date, skip because we don't need to change it
        if "due_at" not in assignment or not assignment["due_at"]:
            continue

        due_at = datetime.datetime.fromisoformat(assignment["due_at"])
        due_at = due_at + datetime.timedelta(days=offset)
        response = requests.put(
            f"{API_URL}/courses/{course_id}/assignments/{assignment['id']}",
            headers=headers,
            json={
                "assignment": {
                    "id": assignment["id"],
                    "due_at": due_at.isoformat()
                }
            })
        if response.status_code == 200:
            print(f"Changed date of {assignment['name']} to {due_at}")
        else:
            print(f"Error changing date of {assignment['name']}")
            print(response.status_code)
            print(response.text)



main()
