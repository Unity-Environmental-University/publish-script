import requests
import json
import re

class CanvasLink:
  def __init__(self, constants_path='constants.json'):
    self.html_url = None
    self.api_url = None
    self.api_token = None
    self.load_constants(constants_path)
    self.headers = {"Authorization": f"Bearer {self.api_token}"}

  def load_constants(self, filepath):
    with open(filepath, 'r') as f:
      constants = json.load(f)
      self.api_token = constants["apiToken"]
      self.api_url = constants["apiUrl"]
      self.html_url = re.sub('/api/v1', '', constants["apiUrl"])

  def get_paged_data(self, url, headers=None):
    if headers is None:
      headers = self.headers
    response = requests.get(url, headers)
    out = response.json()
    next_page_link = "!"
    while len(next_page_link) != 0:
        pagination_links = response.headers["Link"].split(",")
        for link in pagination_links:
          if 'next' in link:
            next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
            print(next_page_link)
            response = requests.get(next_page_link, headers)
            out = out + response.json()
            break
          else:
            next_page_link = ""
    return out

  def get_course_link(self, course_id):
    return CourseLink(canvas_link=self, course_id=course_id)


class CourseLink:
  def __init__(self, fetch=False,*, canvas_link:CanvasLink, course_id):
      self.link = canvas_link
      self.course_id = course_id
      self.data = {}
      if fetch:
        self.fetch_data()

  @property
  def data(self):
    if not self.__data:
      self.__data = self.fetch_data()

    return self.__data

  @data.setter
  def data(self, data):
    self.__data = data

  def fetch_data(self, params=None, headers=None):
    if headers is None:
      headers = self.link.headers
    response = requests.put(f'{self.link.api_url}/courses/{self.course_id}', headers=headers, data=params)
    if not response.ok:
      raise Exception(f"Problem getting course data for {self.course_id}")
    self.data = response.json()
    return self.data

  # naive implementation will likely not work
  def save_data(self, params=None):
    requests.put(f'{self.link.api_url}/courses/{self.course_id}', headers=self.link.headers, data=params.update(self.data))

