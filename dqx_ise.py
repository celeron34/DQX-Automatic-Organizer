from datetime import datetime as dt, timedelta as dt_td
from selenium import webdriver
from re import search

def getTable(browser_path:str=None, driver_path:str=None) -> list[dt]:
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

    raidPngNames = {
        raidPngSearch.group(0) + '.png' for raidPngSearch in map(
            lambda element:search('[0-9]+', element.find_element('xpath', 'a').get_attribute('href')),
            b.find_elements('xpath', '//*[@id="contentArea"]/div/div/div[3]/ul/li')
            )
        }

    table = b.find_element('xpath', '//*[@id="raid-container"]/table/tbody')

    tablePngNames = []
    for tr in table.find_elements('tag name', 'tr')[1:]: # 先頭は日付
        tdPngNames = [
            tdPngSearch.group(0) for tdPngSearch in map(
                lambda td:search('[0-9]+[.]png', td.find_element('xpath', 'img').get_attribute('src')),
                tr.find_elements('tag name', 'td')[1:] # 先頭は時間列
                )
            ]
        print(tdPngNames)
        tablePngNames.append(tdPngNames)

    b.quit()
    
    n = dt.now()
    now = dt(n.year, n.month, n.day, 6, 0, 0, 0)
    if n.hour < 6:
        now -= dt_td(days=1)

    timelist = []
    for i in range(5):
        for j in range(24):
            if tablePngNames[j][i] not in raidPngNames:
                timelist.append(now)
            now += dt_td(hours=1)

    return timelist
