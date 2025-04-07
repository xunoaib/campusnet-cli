#!/usr/bin/env python3
import os
import pickle
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import make_dataclass
from pathlib import Path

import tabulate
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

_course_fields = [
    ('name', str),  # course name
    ('topic', str),  # special topic (if applicable)
] + [(name, str) for name in COURSE_SEC_FIELDS]

Course = make_dataclass('Course', _course_fields)


class CampusNet:

    cachedir = Path(__file__).parent / 'cache'
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

    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.session = requests.Session()

    @property
    def authenticated(self):
        r = self.session.get(
            'https://campusnet.csuohio.edu/sec/personal/persdata.jsp')
        return 'Session Expired' not in r.text

    def login(self, username=None, password=None):
        if username: self.username = username
        if password: self.password = password
        if not self.username or not self.password:
            raise Exception('Missing login credentials')

        paramsPost = {
            "Submit": "Login",
            "pwd": self.password,
            "user": self.username,
            "version": "136.0",
            "backdoor": "N",
            "browser": "Firefox"
        }
        response = self.session.post(
            "https://campusnet.csuohio.edu/ps8verify.jsp",
            data=paramsPost,
            headers=self.headers)

        if 'Login in progress' not in response.text:
            raise Exception('Login failed!\n%s' % response.text)

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

    def find_courses(self, term, subject, acad='GRAD', cache=True):
        '''Retrieves a course list from CampusNet or from local cache'''

        def retrieve_xml():
            if not cache:
                return self._search_courses(term, subject, acad)

            path = self.cachedir / 'search' / f'{term}_{subject}.xml'

            if path.exists():
                return open(path).read()

            path.parent.mkdir(parents=True, exist_ok=True)
            resp_text = self._search_courses(term, subject, acad)

            print('Caching results to', path)
            open(path, 'w').write(resp_text)
            return resp_text

        return parse_course_search_xml(retrieve_xml())

    def _search_courses(self, term, subject, acad):
        '''Retrieves a course list from CampusNet'''

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

        assert response.ok, 'HTTP Error: %d %s' % (
            response.status_code,
            response.text,
        )
        return response.text


def parse_course_search_xml(response_xml: str):
    '''Constructs a dictionary of course names to sections given an XML
    response from the course search endpoint'''

    root = ET.fromstring(response_xml)
    classlist = root.find('ClassList')
    if classlist is None or not classlist.text:
        raise Exception('Expected ClassList tag in search response')

    table = html.fromstring(classlist.text)
    assert table.tag == 'table', f'Expected table tag, got: {table.tag}'

    headings, *rows = [[
        ''.join(td.itertext()).strip() for td in tr.iter('td')
    ] for tr in table.iter('tr')]
    norm_headings = list(map(normalize, headings))

    courses = defaultdict(list)
    name = None
    for r in rows:
        if len(r) == 1:  # course title, ie: CIS  895 Doctoral Research
            name = r[0]
        elif len(r) == 13:  # course info, ie: dates, times, enrollment
            assert name is not None, 'Found section before course name'
            kwargs = {k: v or None for k, v in zip(norm_headings, r) if k}
            courses[name].append(Course(name=name, topic=None, **kwargs))
        elif len(r) == 2 and r[0] == '':  # special topic (has a separate row)
            t = r[1]
            assert t.startswith('Topic: '), f'Expected "Topic:", but got: {t}'
            courses[name][-1].topic = t.split(': ', 1)[-1]
        else:
            assert r == [''] * 3, f'Unexpected row: {r}'

    return dict(courses)


def print_courses(courses: dict[str, list[Course]]):
    table_headers = {
        'Name': lambda s: s.name + (' - ' + s.topic if s.topic else ''),
        'ClassNr': lambda s: s.classnr,
        'Section': lambda s: s.sect,
        'Days': lambda s: s.time,
        'Time': lambda s: s.time,
        'Enrolled': lambda s: s.enrltot,
    }

    table = []
    for sections in courses.values():
        for section in sections:
            table.append([f(section) for f in table_headers.values()])

    print(tabulate.tabulate(table, headers=tuple(table_headers.keys())))


def main():
    terms = ['114-Fall 2025', '115-Spr 2026']
    term = terms[1]
    subject = 'STA'
    subject = 'CIS'

    net = CampusNet(USERNAME, PASSWORD)
    net.login()

    courses = net.find_courses(term, subject, cache=True)

    print_courses(courses)


if __name__ == '__main__':
    main()
