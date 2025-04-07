#!/usr/bin/env python3
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, make_dataclass
from itertools import pairwise
from pathlib import Path

import requests
import tabulate
from dotenv import load_dotenv
from lxml import html

load_dotenv()

# Available acads: UGRD, GRAD, LAW, CNED

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
    sess: str | None


@dataclass
class CourseDetails:
    session: str
    consent: str
    component: str
    status: str
    credits: str
    enrollment: str
    lastdaytoadd: str
    lastdaytodrop: str
    lastdaytowithdraw: str
    description: str


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

    def subjects(self, term, acad=DEFAULT_ACAD, load_cache=True):

        def parse(xml: str):
            root = ET.fromstring(xml)
            subject_list = root.find('SubjectList')
            if subject_list is None:
                return []
            return [c.text for c in subject_list if c.tag == 'Subject']

        path = self.cachedir / f'subjects_{term}_{acad}.txt'

        if load_cache and path.exists():
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

        if load_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(response.text)

        return parse(response.text)

    def terms(self, load_cache=True):
        '''Visits the course search page and returns available terms'''

        path = self.cachedir / 'terms.txt'

        if load_cache and path.exists():
            with open(path) as f:
                return [line.strip() for line in f if line.strip()]

        r = self.session.get(
            'https://campusnet.csuohio.edu/sec/classsearch/search_reg.jsp')

        text_start = '<!--  Display Term Choices'
        text_end = '<!--  Display Career Choices'
        pattern = re.escape(text_start) + '(.*?)' + re.escape(text_end)

        if text := re.search(pattern, r.text, re.DOTALL):
            term_list = re.findall('value="(.*?)"', text.group(1))
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write('\n'.join(term_list))
            return term_list

        raise Exception('Failed to find terms on search registration page')

    def find_courses(self, term, subject, acad=DEFAULT_ACAD, load_cache=True):
        '''Retrieves a course list from CampusNet or from local cache'''

        def retrieve_xml():
            path = self.cachedir / 'search' / f'{term}_{subject}.xml'

            if load_cache and path.exists():
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

    def class_details(self, termNbr, classNbr, acad, load_cache=True):

        def process():
            if load_cache and path.exists():
                return parse_course_details_xml(open(path).read())

            resp_xml = query()
            result = parse_course_details_xml(resp_xml)
            print('Caching results to', path)
            path.parent.mkdir(parents=True, exist_ok=True)
            open(path, 'w').write(resp_xml)
            return result

        def query():
            paramsGet = {
                "classNbr": classNbr,
                "acad": acad,  # required but unused?
                "AJAXClassName": "AJAX.Ajax_ClassSearch",
                "function": "getClassDetails",
                "term": termNbr,
            }
            return self.session.get(
                "https://campusnet.csuohio.edu/AJAX/AJAXMasterServlet",
                params=paramsGet).text

        path = self.cachedir / 'details' / f'{termNbr}_{classNbr}_{acad}.xml'
        return process()


def parse_course_search_xml(response_xml: str) -> dict[str, list[Course]]:
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

    courses = defaultdict(list)
    name = None
    for r in rows:
        if len(r) == 1:  # course title, ie: CIS  895 Doctoral Research
            name = r[0]
        elif len(r) == len(headings):  # course info
            assert name is not None, 'Found section before course name'
            kwargs = {'sess': None}
            kwargs |= {k: v or None for k, v in zip(norm_headings, r) if k}
            courses[name].append(Course(name=name, topic=None, **kwargs))
        elif len(r) == 2 and r[0] == '':  # special topic (has a separate row)
            assert name is not None, 'Found topic before course name'
            t = r[1]
            if t.startswith('Topic: '):
                t = t.split(': ', 1)[-1]
            courses[name][-1].topic = t
        else:
            assert r == [''] * 3, f'Unexpected row: {r}'

    return dict(courses)


def parse_course_details_xml(response_xml: str):
    '''Parses a subset of details for an individual course.
    More data is available but not yet parsed, such as:
        - combined courses
        - description
        - data already available from course search
    '''

    try:
        root = ET.fromstring(response_xml)
    except Exception as exc:
        raise Exception('XML Parse Error: %s' % (response_xml, )) from exc

    error_code = root.find('ErrorCode')
    if error_code is not None:
        raise Exception(f'API Error:\n{response_xml}')

    classdetails = root.find('ClassDetails')
    if classdetails is None or not classdetails.text:
        raise Exception(
            f'Expected ClassDetails tag in search response:\n{response_xml}')

    div = html.fromstring(classdetails.text)
    assert div.tag == 'div', f'Expected div tag, got: {div.tag}'

    # construct top-level "Attribute: Value" mappings
    first_table = div.find('table/tr/td/table')
    first_table_tds = [td.text for td in first_table.iter('td')]

    props = {}
    for td1, td2 in pairwise(first_table_tds):
        if td1 and td1.endswith(':'):
            props[td1[:-1]] = td2.strip()

    # extract course description (very messily)
    for table in div.find('table/tr/td').iter('table'):
        for tr in table.iter('tr'):
            for td in table.iter('td'):
                if items := [t.strip() for t in td.itertext() if t.strip()]:
                    if items[0] == 'Course Description:':
                        props['Description'] = items[1]

    fields = {normalize(k): v for k, v in props.items()}
    return CourseDetails(**fields)


def print_courses(courses: dict[str, list[Course]]):
    table_headers = {
        'Days': lambda s: s.days,
        'Name': lambda s: s.name + (' - ' + s.topic if s.topic else ''),
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

    net = CampusNet(USERNAME, PASSWORD)
    net.login()

    terms = ['114-Fall 2025', '115-Spr 2026']
    # terms = net.terms()

    subjects = ['CIS', 'STA']
    # subjects = net.subjects(terms[1])

    acad = DEFAULT_ACAD

    # r = net._search_courses(terms[0], subjects[0], 'GRAD')
    # print(r)
    # exit()
    #
    # print(net.class_details('114', '2644', acad='GRAD'))
    # print(net.class_details('115', '5118', acad='GRAD'))

    # retrieve high-level course listings
    all_sections = []
    for term in terms:
        # subjects = net.subjects(term)  # ALL subjects
        for subject in subjects:
            courses = net.find_courses(term,
                                       subject,
                                       acad=acad,
                                       load_cache=True)
            print(f'\n\033[93;1m# {term}: {subject}\033[0m\n')
            print_courses(courses)

            # add to all sections
            for sections in courses.values():
                all_sections += [(term, subject, section)
                                 for section in sections]

    # retrieve course details
    for term, subject, section in all_sections:
        if not section.classnr:
            print(
                f'\033[93mWARN: Course {section.name} is missing a course number\033[0m'
            )
            continue
        try:
            termNbr = term.split('-')[0]
            details = net.class_details(termNbr, section.classnr, acad)
        except Exception as exc:
            raise Exception(
                f'Error parsing course details for: {term} {subject} {section}'
            )


if __name__ == '__main__':
    main()
