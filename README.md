# 📚 CampusNet Scraper

A command-line tool for scraping course listings and details from **Cleveland State University's CampusNet**.
Supports retrieving available terms, subjects, courses, and detailed section information.

## Features

* Log in with your CampusNet credentials
* List available terms and subjects
* Retrieve all courses for given subjects/terms
* Fetch detailed section information (course numbers, instructors, enrollment, etc.)
* Tabular output with `tabulate`
* Optional caching for faster repeated queries

## Environment Variables

You should define your CampusNet credentials using the following environment variables (or pass them as arguments).
These can be set directly in your shell or placed in a `.env` file at the project root.

```env
CSU_USERNAME=your_username
CSU_PASSWORD=your_password
DEFAULT_ACAD=UGRD
```

* `CSU_USERNAME` – your CampusNet username
* `CSU_PASSWORD` – your CampusNet password
* `DEFAULT_ACAD` – optional; academic level (`UGRD`, `GRAD`, `LAW`, `CNED`). Defaults to `GRAD`.

## Usage

Run with Python:

```
usage: campusnet.py [-h] [--username USERNAME] [--password PASSWORD]
                    [--terms [TERMS ...]] [--subjects [SUBJECTS ...]]
                    [--acad ACAD] [--no-cache] [--format {table,object}]

Retrieve course listings and details from CampusNet.

options:
  -h, --help            show this help message and exit
  --username USERNAME   Your CampusNet username
  --password PASSWORD   Your CampusNet password
  --terms, -t [TERMS ...]
                        List of terms (e.g., '114-Fall 2025')
  --subjects, -s [SUBJECTS ...]
                        List of subjects (e.g., 'CIS', 'STA')
  --acad ACAD           Academic career level (e.g., 'GRAD', 'UGRD')
  --no-cache, -n        Disable cache usage for course listings
  --format, -f {table,object}
                        Course output format (default: table)
```

## Examples

```sh
# List available terms (semesters)
python campusnet.py --terms

# List available subjects for the given term(s)
python campusnet.py --terms '114-Fall 2025' --subjects

# List courses for the given subject(s) and term(s)
python campusnet.py --terms '114-Fall 2025' --subjects CIS

# List courses with more detail (as objects)
python campusnet.py --terms '114-Fall 2025' --subjects CIS --format object
```
