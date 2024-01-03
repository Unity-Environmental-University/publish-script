import requests
import json


class CanvasLink:
  def __init__(self, constants_path='constants.json'):
    self.headers = {"Authorization": f"Bearer {api_token}"}
    self.load_constants(self, constants_path)

  def load_constants(self, filepath):
    with open(filepath, 'r') as f:
        constants = json.load(f)
      self.api_token = constants["apiToken"]
      self.api_url = constants["apiUrl"]
      self.html_url = re.sub('\/api\/v1', '', constants["apiUrl"])

  def get_paged_data(self, url, headers=self.HEADERS):
    response = requests.get(url, headers)
    out = response.json()
    next_page_link = "!"
    while len(next_page_link) != 0:
        pagination_links = response.headers["Link"].split(",")
        for link in pagination_links:
          if 'next' in link:
            next_page_link = link.split(";")[0].split("<")[1].split(">")[0]
            log(next_page_link)
            response = requests.get(next_page_link, headers)
            out = out + response.json()
            break
          else:
            next_page_link = ""

  def get_course_link(self, course_id)
    return CourseLink(canvas_link=self, course_id=course_id)

  return out

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
        self.__data = fetch_data(self)

      return self.__data

    @data.setter
    def data(self, data):
      self.__data = data

    def fetch_data(self, params={}):
      requests.put(f'{self.link.API_URL}/courses/{self.course_id}', headers=self.link.HEADERS, data=params)
      if not response.ok:
        raise Exception(f"Problem getting course data for {self.course_id}")
      self.data = requests.json()
      return self.data

    # naive implementation will likely not work
    def save_data(self, params={}):
      requests.put(f'{self.link.API_URL}/courses/{self.course_id}', headers=self.link.HEADERS, data=params.update(self.data))

