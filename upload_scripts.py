from datetime import datetime
import requests
import publish_script
import subprocess
from publish_script import Course
import os
import json
publish_script.load_constants('constants.json')
course = Course.get_by_code('LXD_TOOL000')


def main():
    result = subprocess.run(
        ['git', 'ls-tree', '--full-tree', '-r', '--name-only', 'HEAD'],
        capture_output=True,
        text=True
    )
    print(result)
    print('run')
    output = result.stdout
    if not output:
        print(result.stderr)

    file_names = output.split('\n')
    api_link = course.api_link
    last_uploaded = 0
    with open('upload.json', 'r') as file:
        full_upload_data = json.load(file)

    upload_data = {}
    upload_files = []
    for file_name in file_names:
        print(file_name)
        if len(file_name) == 0:
            continue
        with open(file_name, 'rb') as f:
            files = {"file": f}

            file_last_saved = os.path.getmtime(file_name)
            if file_last_saved > last_uploaded:
                response = requests.post(
                    f'{api_link.api_url}/{course.content_url_path}/files',
                    files=files, headers=api_link.headers,
                    data={
                    "name": os.path.basename(file_name),
                    "no_redirect": True,
                    "parent_folder_path": f'publish_tools/{os.path.dirname(file_name)}',
                    "on_duplicate": "overwrite"
                })
                print(response)
                response_data = response.json()
                print(response_data)
                url = response_data["upload_url"]

                response = requests.post(url, files={'file': open(file_name, 'rb')}, data=response_data['upload_params'])
                print(response)
                if not response.ok:
                    print(response.text)

                upload_files.append(file_name)

        if response.is_redirect:
            requests.Session().send(response.next)

    last_saved = datetime.now()

    upload_data = {
        'files': upload_files,
        'last_saved': last_saved
    }

    full_upload_data.append(upload_data)
    json.dump(upload_data, open('upload.json', 'w'))


if __name__ == '__main__':
    main()