#!/usr/bin/env python3
import os
import pickle
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

from dotenv import load_dotenv
from lxml import html

load_dotenv()

USERNAME = os.environ.get('CSU_USERNAME')
PASSWORD = os.environ.get('CSU_PASSWORD')

assert USERNAME and PASSWORD

import requests


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

    courses = pickle.load(open(courses_pkl, 'rb'))

    classList = next(iter(courses)).text
    table = html.fromstring(classList)

    headings, *rows = [[
        ''.join(td.itertext()).strip() for td in tr.iter('td')
    ] for tr in table.iter('tr')]

    # group sections by course
    d = defaultdict(list)
    course = None
    for r in rows:
        if len(r) == 1:  # course title, ie: CIS  895 Doctoral Research
            course = r[0]
        elif len(r) == 13:
            d[course].append(r)

    for course, sections in d.items():
        print()
        print(course)
        print()
        for s in sections:
            s = [v if v else None for v in s]
            s = dict(zip(headings, s))
            print('   ', s)

    return


if __name__ == '__main__':
    main()
