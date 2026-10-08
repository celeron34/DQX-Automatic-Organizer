from dataclasses import dataclass
from datetime import datetime as dt, timedelta as dt_td
from pathlib import PurePosixPath
from re import search
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


@dataclass(frozen=True)
class DefenseScheduleEntry:
    datetime: dt
    force_id: int
    is_all_forces: bool


def build_schedule_entries(
    table_png_names: list[list[str | None]], start_at: dt, force_ids: set[int]
) -> list[DefenseScheduleEntry]:
    """Associate each schedule icon with its datetime and current force ID.

    The page's current force list supplies the IDs for regular forces. An icon
    absent from that list represents the all-forces schedule slot.
    """
    if not table_png_names:
        return []

    entries = []
    for day_index in range(len(table_png_names[0])):
        for hour_index, row in enumerate(table_png_names):
            icon_name = row[day_index]
            if icon_name is None:
                continue
            id_match = search(r'([0-9]+)[.]png', icon_name)
            if id_match is None:
                continue
            force_id = int(id_match.group(1))
            entries.append(DefenseScheduleEntry(
                datetime=start_at + dt_td(days=day_index, hours=hour_index),
                force_id=force_id,
                is_all_forces=force_id not in force_ids,
            ))
    return entries


def get_file_names(parent: Any, xpath: str, attribute: str = 'src') -> list[str]:
    """Return file basenames from an XPath-selected set of elements.

    `attribute` may be `src`, `href`, or another URL/path-valued attribute.
    Query strings and fragments are ignored, and duplicate names are retained
    in document order.
    """
    file_names = []
    for element in parent.find_elements('xpath', xpath):
        value = element.get_attribute(attribute)
        if not value:
            continue
        path = urlparse(value).path
        if not path or path.endswith('/'):
            continue
        filename = PurePosixPath(unquote(path)).name
        if filename:
            file_names.append(filename)
    return file_names


def get_force_ids(parent: Any) -> set[int]:
    """Read the currently listed force IDs from the page's filter links."""
    force_ids = set()
    xpath = '//*[@id="contentArea"]//a[contains(@href, "defense_force_num=")]'
    for element in parent.find_elements('xpath', xpath):
        href = element.get_attribute('href')
        if not href:
            continue
        for value in parse_qs(urlparse(href).query).get('defense_force_num', []):
            try:
                force_ids.add(int(value))
            except ValueError:
                continue
    return force_ids


def getTable(browser_path:str=None, driver_path:str=None) -> list[DefenseScheduleEntry]:
    from selenium import webdriver

    options = webdriver.ChromeOptions()
    if browser_path:
        options.binary_location = browser_path
    options.add_argument('--headless')

    if driver_path:
        service = webdriver.ChromeService(executable_path=driver_path)
        b = webdriver.Chrome(options, service)
    else:
        b = webdriver.Chrome(options)

    b.get('https://hiroba.dqx.jp/sc/tokoyami/')

    force_ids = get_force_ids(b)
    table = b.find_element('xpath', '//*[@id="raid-container"]/table/tbody')

    tablePngNames = []
    for tr in table.find_elements('tag name', 'tr')[1:]: # 先頭は日付
        tdPngNames = []
        for td in tr.find_elements('tag name', 'td')[1:]: # 先頭は時間列
            file_names = get_file_names(td, './/img', 'src')
            pngSearch = search(r'[0-9]+[.]png', file_names[0]) if file_names else None
            tdPngNames.append(pngSearch.group(0) if pngSearch else None)
        print(tdPngNames)
        tablePngNames.append(tdPngNames)

    b.quit()
    
    n = dt.now()
    now = dt(n.year, n.month, n.day, 6, 0, 0, 0)
    if n.hour < 6:
        now -= dt_td(days=1)

    # tablePngNames follows the page's 24-hour rows and five date columns.
    return build_schedule_entries(tablePngNames, now, force_ids)
