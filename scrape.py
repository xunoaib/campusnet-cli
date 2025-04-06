#!/usr/bin/env python3

import os

from dotenv import load_dotenv

load_dotenv()

USERNAME = os.environ.get('CSU_USERNAME')
PASSWORD = os.environ.get('CSU_PASSWORD')

assert USERNAME and PASSWORD

import requests


class CampusNet:

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
        headers = {
            "Origin": "https://campusnet.csuohio.edu",
            "Accept":
            "text/html,application/xhtml xml,application/xml;q=0.9,*/*;q=0.8",
            "Priority": "u=0, i",
            "User-Agent":
            "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Connection": "keep-alive",
            "Referer": "https://campusnet.csuohio.edu/login.jsp",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-User": "?1",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = self.session.post(
            "https://campusnet.csuohio.edu/ps8verify.jsp",
            data=paramsPost,
            headers=headers)

        if 'Login in progress' not in response.text:
            raise Exception('Login failed!')


def main():
    c = CampusNet()
    c.login(USERNAME, PASSWORD)


if __name__ == '__main__':
    main()
