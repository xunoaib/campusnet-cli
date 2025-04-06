#!/usr/bin/env python3
import os
import pickle
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import make_dataclass

from dotenv import load_dotenv
from lxml import html

load_dotenv()

USERNAME = os.environ.get('CSU_USERNAME')
PASSWORD = os.environ.get('CSU_PASSWORD')

assert USERNAME and PASSWORD

import requests


def normalize(s: str):
    s = s.strip().lower()
    return re.sub(r'\W|^(?=\d)', '', s)


COURSE_SEC_FIELDS = list(
    map(normalize, [
        'Enrl.', 'Det.', 'ClassNr', 'Sect.', 'Begin Date - End Date', 'Days',
        'Time', 'Room', 'Instructor', 'Comp.', 'Stat.', 'Enrl/Tot'
    ]))

_course_fields = [('name', str)] + [(name, str) for name in COURSE_SEC_FIELDS]
Course = make_dataclass('Course', _course_fields)


class CampusNet:

    headers = {
        "Accept": "*/*",
        "Priority": "u=0",
        "User-Agent":
        "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Connection": "keep-alive",
        "Referer":
        "https://campusnet.csuohio.edu/sec/classsearch/search_reg.jsp",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Site": "same-origin",
        "Accept-Language": "en-US,en;q=0.5",
        "Sec-Fetch-Mode": "cors"
    }

    def __init__(self):
        self.session = requests.Session()

    def login(self, username, password):
        paramsPost = {
            "Submit": "Login",
            "pwd": password,
            "user": username,
            "version": "136.0",
            "backdoor": "N",
            "browser": "Firefox"
        }
        response = self.session.post(
            "https://campusnet.csuohio.edu/ps8verify.jsp",
            data=paramsPost,
            headers=self.headers)

        if 'Login in progress' not in response.text:
            raise Exception('Login failed!')

    def subject_list(self, term, acad='GRAD'):
        paramsGet = {
            "college": "",
            "subject": "",
            "function": "getSubjectsRegular",
            "acad": acad,
            "AJAXClassName": "AJAX.Ajax_ClassSearch",
            "location": "",
            "term": term,
            "sid": "0.47412165428294384"
        }
        response = self.session.get(
            "https://campusnet.csuohio.edu/AJAX/AJAXMasterServlet",
            params=paramsGet,
            headers=self.headers)

        return response.text  # XML

    def get_terms(self):
        '''visits the search registration page showing available terms'''

        r = self.session.get(
            'https://campusnet.csuohio.edu/sec/classsearch/search_reg.jsp')

        text_start = '<!--  Display Term Choices'
        text_end = '<!--  Display Career Choices'
        pattern = re.escape(text_start) + '(.*?)' + re.escape(text_end)

        if text := re.search(pattern, r.text, re.DOTALL):
            return re.findall('value="(.*?)"', text.group(1))

        raise Exception('Failed to find terms on search registration page')

    def search_courses(self, term, subject, acad='GRAD'):
        paramsGet = {
            "thu": "N",
            "tue": "N",
            "subject": subject,
            "sat": "N",
            "AJAXClassName": "AJAX.Ajax_ClassSearch",
            "starttime": "ALL",
            "acadVal": acad,
            "mon": "N",
            "sun": "N",
            "sid": "0.6793350056780008",
            "termVal": term,
            "function": "getClasessResults",
            "wed": "N",
            "location": "ALL",
            "locations": "undefined",
            "fri": "N",
            "incl": "I"
        }
        response = self.session.get(
            "https://campusnet.csuohio.edu/AJAX/AJAXMasterServlet",
            params=paramsGet,
            headers=self.headers)

        return ET.fromstring(response.text)


def parse_course_results(course_tree: ET.Element):

    classList = next(iter(course_tree)).text
    table = html.fromstring(classList)

    headings, *rows = [[
        ''.join(td.itertext()).strip() for td in tr.iter('td')
    ] for tr in table.iter('tr')]

    norm_headings = list(map(normalize, headings))

    # group sections by course
    courses = defaultdict(list)
    name = None
    for r in rows:
        if len(r) == 1:  # course title, ie: CIS  895 Doctoral Research
            name = r[0]
        elif len(r) == 13:
            assert name is not None, 'Found section before course name'
            kwargs = {k: v or None for k, v in zip(norm_headings, r) if k}
            courses[name].append(Course(name=name, **kwargs))

    return dict(courses)


def main():
    terms = ['114-Fall 2025', '115-Spr 2026']
    term = terms[0]
    subject = 'STA'
    subject = 'CIS'

    courses_pkl = f'{term}_{subject}.pkl'

    if not os.path.exists(courses_pkl):
        print('Logging into campusnet...')
        c = CampusNet()
        c.login(USERNAME, PASSWORD)
        r = c.search_courses(term, subject)
        print('Writing cache to', courses_pkl)
        pickle.dump(r, open(courses_pkl, 'wb'))

    course_tree = pickle.load(open(courses_pkl, 'rb'))
    courses = parse_course_results(course_tree)

    print(courses)


if __name__ == '__main__':
    main()
