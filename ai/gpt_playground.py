import random
import asyncio
try:
    from openai import OpenAI
except ImportError:
    exit("Please install openai first.")

import json

import publish_script
from publish_script import Course

publish_script.load_constants('../constants.json')
constants = json.load(open('../constants.json'))
OPENAI_API_KEY = constants['openApiKey']

async def main():
    await interactive_chat()


async def interactive_chat():
    thread_id = constants['threadId'] if 'threadId' in constants.keys() else None
    assistant_id = constants['assistantId'] if 'assistantId' in constants.keys() else None
    thread = None
    client = OpenAI(api_key=OPENAI_API_KEY)
    if assistant_id:
        assistant = client.beta.assistants.retrieve(assistant_id)
    else:
        assistant = client.beta.assistants.create(
            name="Spanish Tutor 2",
            instructions="You only speak in spanish, using a library of only 300 words. You want to help me learn "+
            "spanish, and understand english perfectly. You do not say goodbye every time I thank you. " +
            "You are deeply reluctant and refuse to speak in any language that is not spanish, beyond single word translations. " +
            "When someone speaks english to you, you politely refuse to answer " +
            "beyond telling them how to phrase the question in espanol.",
            model="gpt-3.5-turbo",
            tools=[{"type": "code_interpreter"}],
        )
    if thread_id is not None:
        thread = client.beta.threads.retrieve(thread_id)
    else:
        thread = client.beta.threads.create()

    thread_id = thread.id

    with open(f"../output/{thread_id}.txt", "a") as f:
        f.write(f'Thread: {thread_id}\n')
        f.write(f'Assistant: {assistant.name}, {assistant.id}\n')

    print(thread_id)
    while True:
        text = input(f"ask {assistant.name}:")
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            content=text,
            role='user',
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant.id
        )

        run_info = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

        while run_info.status != "completed":
            run_info = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

        messages = client.beta.threads.messages.list(message.thread_id)
        message_content = messages.data[0].content[0].text.value
        with open(f"../output/{assistant.id}.txt", "a") as f:
            f.write(f"User: {text}\n")
            f.write(f"Assistant: {message_content}\n")
        print(message_content)



def get_project_descriptions_and_overviews():
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


if __name__ == '__main__':
    asyncio.run(main())
