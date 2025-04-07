#!/usr/bin/env python3
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, make_dataclass
from pathlib import Path

import requests
import tabulate
from dotenv import load_dotenv
from lxml import html

load_dotenv()

USERNAME = os.environ.get('CSU_USERNAME')
PASSWORD = os.environ.get('CSU_PASSWORD')
DEFAULT_ACAD = os.environ.get('DEFAULT_ACAD', 'GRAD')


@dataclass
class Course:
    name: str | None
    topic: str | None
    enrl: str | None
    det: str | None
    classnr: str | None
    sect: str | None
    begindateenddate: str | None
    days: str | None
    time: str | None
    room: str | None
    instructor: str | None
    comp: str | None
    stat: str | None
    enrltot: str | None


def generate_course_class():
    '''This can help regenerate course fields if they ever change'''

    headings = list(
        map(normalize, [
            'Enrl.', 'Det.', 'ClassNr', 'Sect.', 'Begin Date - End Date',
            'Days', 'Time', 'Room', 'Instructor', 'Comp.', 'Stat.', 'Enrl/Tot'
        ])) + ['name', 'topic']

    fields = [(f, str) for f in headings]
    return make_dataclass('Course', fields)


def normalize(s: str):
    s = s.strip().lower()
    return re.sub(r'\W|^(?=\d)', '', s)


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

    def subjects(self, term, acad=DEFAULT_ACAD, cache=True):

        def parse(xml: str):
            root = ET.fromstring(xml)
            subject_list = root.find('SubjectList')
            if subject_list is None:
                return []
            return [c.text for c in subject_list if c.tag == 'Subject']

        path = self.cachedir / f'subjects_{term}_{acad}.txt'

        if cache and path.exists():
            with open(path) as f:
                return parse(f.read())

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

        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(response.text)

        return parse(response.text)

    def terms(self, cache=True):
        '''Visits the course search page and returns available terms'''

        path = self.cachedir / 'terms.txt'

        if cache and path.exists():
            with open(path) as f:
                return [line.strip() for line in f if line.strip()]

        r = self.session.get(
            'https://campusnet.csuohio.edu/sec/classsearch/search_reg.jsp')

        text_start = '<!--  Display Term Choices'
        text_end = '<!--  Display Career Choices'
        pattern = re.escape(text_start) + '(.*?)' + re.escape(text_end)

        if text := re.search(pattern, r.text, re.DOTALL):
            term_list = re.findall('value="(.*?)"', text.group(1))
            if cache:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w') as f:
                    f.write('\n'.join(term_list))
            return term_list

        raise Exception('Failed to find terms on search registration page')

    def find_courses(self, term, subject, acad=DEFAULT_ACAD, cache=True):
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

    error_code = root.find('ErrorCode')
    if error_code is not None:
        if error_code.text == 'CSTCLS_NOCL2':
            print('WARNING: No classes found')
            return {}
        raise Exception(f'API Error:\n{response_xml}')

    classlist = root.find('ClassList')
    if classlist is None or not classlist.text:
        raise Exception(
            f'Expected ClassList tag in search response:\n{response_xml}')

    table = html.fromstring(classlist.text)
    assert table.tag == 'table', f'Expected table tag, got: {table.tag}'

    headings, *rows = [[
        ''.join(td.itertext()).strip() for td in tr.iter('td')
    ] for tr in table.iter('tr')]
    norm_headings = list(map(normalize, headings))

    print(headings)

    _fields = [(f, str) for f in norm_headings + ['name', 'topic'] if f]
    Section = make_dataclass('Section', _fields)

    courses = defaultdict(list)
    name = None
    for r in rows:
        print(r, len(r))
        if len(r) == 1:  # course title, ie: CIS  895 Doctoral Research
            name = r[0]
        elif len(r) == len(headings):  # course info
            assert name is not None, 'Found section before course name'
            kwargs = {k: v or None for k, v in zip(norm_headings, r) if k}
            courses[name].append(Section(name=name, topic=None, **kwargs))
        elif len(r) == 2 and r[0] == '':  # special topic (has a separate row)
            assert name is not None, 'Found topic before course name'
            t = r[1]
            assert t.startswith('Topic: '), f'Expected "Topic:", but got: {t}'
            courses[name][-1].topic = t.split(': ', 1)[-1]
        else:
            assert r == [''] * 3, f'Unexpected row: {r}'

    return dict(courses)


def print_courses(courses: dict[str, list[Course]]):
    table_headers = {
        'Name': lambda s: s.name + (' - ' + s.topic if s.topic else ''),
        'Days': lambda s: s.days,
        'Time': lambda s: s.time,
        'Enrolled': lambda s: s.enrltot,
        'ClassNr': lambda s: s.classnr,
        'Section': lambda s: s.sect,
    }

    table = []
    for sections in courses.values():
        for section in sections:
            table.append([f(section) for f in table_headers.values()])

    print(tabulate.tabulate(table, headers=tuple(table_headers.keys())))


def main():
    terms = ['114-Fall 2025', '115-Spr 2026']
    subjects = ['CIS', 'STA']
    acads = ['UGRD', 'GRAD', 'LAW', 'CNED']

    net = CampusNet(USERNAME, PASSWORD)
    net.login()

    terms = net.terms()
    subjects = net.subjects(terms[1])

    for term in terms:
        for subject in subjects:
            courses = net.find_courses(term,
                                       subject,
                                       acad=DEFAULT_ACAD,
                                       cache=True)
            print(f'\n\033[93;1m# {term}: {subject}\033[0m\n')
            print_courses(courses)


if __name__ == '__main__':
    main()
