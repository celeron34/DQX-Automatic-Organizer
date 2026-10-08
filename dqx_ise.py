from dataclasses import dataclass
from datetime import datetime as dt, timedelta as dt_td
from pathlib import PurePosixPath
from re import search
from typing import Any
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class DefenseScheduleEntry:
    datetime: dt
    force_id: int
    force_name: str


DEFENSE_FORCE_NAMES = {
    2: '闇朱の獣牙兵団',
    3: '紫炎の鉄機兵団',
    4: '深碧の造魔兵団',
    6: '蒼怨の屍獄兵団',
    8: '銀甲の凶蟲兵団',
    9: '翠煙の海妖兵団',
    10: '灰塵の竜鱗兵団',
    11: '彩虹の粘塊兵団',
    12: '芳墨の華烈兵団',
    13: '白雲の冥翼兵団',
    14: '腐緑の樹葬兵団',
    15: '青鮮の菜果兵団',
    16: '鋼塊の重滅兵団',
    17: '金神の遺宝兵団',
    18: '紅爆の暴賊兵団',
    19: '冥黒の悪夢兵団',
    20: '全兵団',
}


def build_schedule_entries(
    table_png_names: list[list[str | None]], start_at: dt
) -> list[DefenseScheduleEntry]:
    """Associate each table icon with its scheduled datetime and force."""
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
                force_name=DEFENSE_FORCE_NAMES.get(force_id, f'不明な兵団 ({force_id})'),
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
    # The legend identifies the force icon IDs; icon 20 is the all-forces slot.
    return build_schedule_entries(tablePngNames, now)
