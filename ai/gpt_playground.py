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


def demo():
    """
    Demo from OpenAI on interacting with client
    """

    client = OpenAI(api_key=OPENAI_API_KEY)

    completion = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content":
                "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
            {"role": "user", "content": "Compose a poem that explains the concept of recursion in programming."}
        ]
    )
    print(json.dumps(list(map(lambda a: str(a.message.content), completion.choices)), indent=2))


async def interactive_chat():
    client = OpenAI(api_key=OPENAI_API_KEY)
    assistant = client.beta.assistants.create(
        name="Demo",
        instructions="You only speak in spanish, using a library of only 300 words. You want to help me learn spanish, and understand english perfectly. You do not say goodbye every time I thank you.",
        model="gpt-4-turbo-preview",
        tools=[{"type": "code_interpreter"}],
    )
    thread = client.beta.threads.create()
    with open(f"../output/{thread.id}.txt", "a") as f:
        f.write(f'Thread: {thread.id}\n')
        f.write(f'Assistant: {assistant.name}, {assistant.id}\n')

    print(thread.id)
    while True:
        text = input(":")
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            content=text,
            role='user',
        )

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        run_info = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )



        while run_info.status != "completed":
            run_info = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

        messages = client.beta.threads.messages.list(message.thread_id)
        message_content = messages.data[0].content[0].text.value
        with open(f"../output/{assistant.id}.txt", "a") as f:
            f.write(message_content + '\n')
        print(message_content)


async def main():
    await interactive_chat()


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
