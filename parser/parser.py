# -*- coding: utf-8 -*-
from typing import Set, Union

import requests
import json
import re
import codecs
from lxml import html

lehrformStrings = {
    "PS": [u"Projekt", u"Seminar"],
    "V": [u"Vorlesung"],
    "S": [u"Seminar"],
    "BS": [u"Seminar"],
    "SP": [u"Seminar", u"Projekt"],
    "VU": [u"Vorlesung", u"Übung"],
    "VP": [u"Vorlesung", u"Projekt"],
    "MP": False
    # more?
}


vertiefungStrings = {
    "Internet &amp; Security Technology": u"IST",
    "Software Architecture &amp; Modeling Technology": u"SAMT",
    "Operating Systems &amp; Information Systems Technology": u"OSIS",
    "Business Process &amp; Enterprise Technology": u"BPET",
    "Human Computer Interaction &amp; Computer Graphics Technology": u"HCT"
}

itseStrings = {
    "IT-Systems Engineering A": u"ITSE",
    "IT-Systems Engineering B": u"ITSE",
    "IT-Systems Engineering C": u"ITSE",
    "IT-Systems Engineering D": u"ITSE"
}


def semester_url(semester_name):
    # returns list of courses for semester
    if semester_name == "now":
        return "https://hpi.de/studium/lehrveranstaltungen/it-systems-engineering-ma.html"

    year = int(semester_name.lstrip("wWsS"))
    assert year < 100, "You have been using this program far too long. Please start coding a new one."
    year_string = f'{year:02}'
    if semester_name.lower().startswith("ws"):
        next_year_string = f'/{year + 1:02}' if year < 19 else str(year + 1)
    else:
        next_year_string = ""
    semester_string = "sommersemester" if semester_name.lower().startswith("ss") else "wintersemester"
    url = f"http://hpi.de/studium/lehrveranstaltungen/archiv/{semester_string}-20{year_string}{next_year_string}.html"
    return url


def scrape_course_urls(overview_page_url):
    # return urls for courses
    response = requests.get(overview_page_url)

    tree = html.fromstring(response.content)
    itse_ma_table = tree.xpath('//h1[text() = "IT-Systems Engineering MA"]/following-sibling::table[1]')[0]
    links = itse_ma_table.xpath('descendant::a[@class="courselink"]/@href')

    return links


def scrape_course_pages(urls):
    # returns dictionary of all courses
    lvs = {}
    i = 0
    for url in urls:
        lvDict = scrape_course_page("http://www.hpi.de/" + url)
        if not lvDict:
            continue
        name = lvDict['nameLV']
        lvs[name] = lvDict
        print(f"{i}\t{name}")
        i += 1
    return lvs


def scrape_course_page(url):
    # returns dictionary containing information about the course
    request = requests.get(url)
    tree = html.fromstring(request.content)

    ################################################################################
    ##                                                                            ##
    ##                    Detection of name and semester                          ##
    ##                                                                            ##
    ################################################################################


    title = tree.xpath('//div[@class="tx-ciuniversity-course"]/h1/text()')[0]

    headerPattern = re.compile(
        """(.*?) \((?:(Sommersemester) \d{2}(\d{2})|(Wintersemester) \d{2}(\d{2})/\d{2}(\d{2}))\)""")
    headerfind = re.search(headerPattern, title)
    nameofLV = headerfind.group(1)

    if (headerfind.group(2) == "Sommersemester"):
        semester = "ss" + headerfind.group(3)
    else:
        assert headerfind.group(4) == "Wintersemester"
        semester = "ws" + headerfind.group(5) + "/" + headerfind.group(6)

    ################################################################################
    ##                                                                            ##
    ##                    Detection of Dozents                                    ##
    ##                                                                            ##
    ################################################################################

    lecturers = tree.xpath('//div[@class="tx-ciuniversity-course"]/i/a/text()')
    lecturers = [x.strip() for x in lecturers if x[0] != '(' and not x.startswith("http")]

    ################################################################################
    ##                                                                            ##
    ##                    Detection of ECTS Points                                ##
    ##                                                                            ##
    ################################################################################

    # line = next(page).decode('utf-8')

    course_general_info = tree.xpath('//*[@class="tx-ciuniversity-course-general-info"]')[0]
    ects_text = course_general_info.xpath('li[2]/text()')[0]

    ects = int(ects_text[len("ECTS: "):])

    ################################################################################
    ##                                                                            ##
    ##                    Detection if benotet or not                             ##
    ##                                                                            ##
    ################################################################################

    is_graded_text = course_general_info.xpath('li[3]/text()')[0][len('Benotet: '):].strip()
    benotet = (is_graded_text == "Ja")
    assert is_graded_text in ["Ja", "Nein"]

    ################################################################################
    ##                                                                            ##
    ##                    Detection of Lehrform                                   ##
    ##                                                                            ##
    ################################################################################

    lehrform = course_general_info.xpath('li[starts-with(text(), "Lehrform")]/text()')
    if len(lehrform) == 0:
        return  # Master's projects are not included
    lehrform = lehrform[0][len('Lehrform: '):]

    ################################################################################
    ##                                                                            ##
    ##                    Detection of Modules & Kennung                          ##
    ##                                                                            ##
    ################################################################################

    ssks = (
        "Recht und Wirtschaft",
        "Kommunikation",
        "Design Thinking Advanced",
        "Design Thinking Basic",
        "Management und Leitung",
    )
    modules = tree.xpath(
        '//*[contains(@class, "tx_dscclipclap") and starts-with(normalize-space(), "IT-Systems Engineering MA")]'
        '/ul/li/text()')  # e.g. ISAE-Konzepte und Methoden

    module_groups: Set[Union[str, str]] = set()  # e.g. BPET, OSIS
    for module in modules:
        if module in ssks:
            module_groups.add("SSK")
        else:
            abbreviation = module[:4].upper()
            module_groups.add(abbreviation)

    ################################################################################
    ##                                                                            ##
    ##                    Try to find good kurz                                   ##
    ##                                                                            ##
    ################################################################################

    maxLineLength = 20
    relevantWords = [x[:maxLineLength] for x in nameofLV.split(" ") if len(x) > 3 or x.upper() == x]
    kurz = ""
    i = 0
    while (i < 2):
        charCount = 0
        while (len(relevantWords) > 0):
            kurzWort = relevantWords.pop(0)
            if (len(kurzWort) <= maxLineLength - charCount):
                charCount += len(kurzWort)
                kurz += kurzWort + " "
            else:
                if (i == 0):
                    relevantWords = [kurzWort] + relevantWords
                    kurz += "<br />"
                break
        i += 1

    # create dictionary for json serialization
    lv = {}
    lv['kurz'] = kurz
    lv['nameLV'] = nameofLV
    lv['semester'] = semester
    lv['dozent'] = lecturers
    # lv['kennung'] = kennung
    lv['modulgruppen'] = list(module_groups)
    lv['cp'] = ects
    lv['benotet'] = benotet
    lv['modul'] = modules
    lv['lehrform'] = lehrform
    return lv


semester = input("Please input the wanted semester: now OR (SS|WS)[0-9]{2}: ")

lvs = scrape_course_pages(scrape_course_urls(semester_url(semester)))
actual_semester = next(iter(lvs.values()))['semester']
path = "./" + actual_semester + ".json"
with codecs.open(path, "w", encoding='utf-8') as f:
    f.write(json.dumps(lvs, ensure_ascii=False, indent=4))
print(f'\nWrote to {path}')
