#!/usr/bin/env python3
import os
import re

from dotenv import load_dotenv

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


def main():
    c = CampusNet()
    c.login(USERNAME, PASSWORD)
    terms = c.get_terms()
    print('Terms:', terms)


if __name__ == '__main__':
    main()
