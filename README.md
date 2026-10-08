# DQX-Automatic-Organizer

## Tests

```sh
python -m pip install py-cord selenium
python -m unittest discover -s test -v
```

UIテストは実際のPycord ViewとDiscord通信のモックを使用します。
Botの起動、トークン、Discordやタイムテーブルへの接続は不要です。

## Clone
```sh
git clone https://github.celeron34.DQX_Automatic_Organizer <Path>
```

## Timetable Scraping

`dqx_ise.getTable(browser_path=None, driver_path=None)` scrapes the DQX defense schedule and returns a list of `DefenseScheduleEntry` values. Selenium is imported only when `getTable` is called; the parsing helpers and unit tests do not require a browser session.

| Field | Type | Meaning |
|---|---|---|
| `datetime` | `datetime` | Scheduled date and time |
| `force_id` | `int` | Defense force ID read from the current page |
| `is_all_forces` | `bool` | Whether the ID is absent from the force links currently listed on the page |

The force ID is read from the page each time. It is not mapped to a fixed force name because the page's IDs can change. `main.py` currently adds only entries where `is_all_forces` is true to its timetable.

```python
from dqx_ise import getTable

for entry in getTable():
    print(entry.datetime, entry.force_id, entry.is_all_forces)
```

For custom XPath/attribute extraction, `get_file_names(parent, xpath, attribute="src")` returns URL-decoded basenames in document order, ignoring query strings and fragments. For example, `get_file_names(cell, ".//a", "href")` can extract names from link targets.

## Config

`config.json`
```json
{ [
    "guild_id" : <guild_id : int>,
    "party_channel_id" : <party_channel_id : int>,
    "role_emoji" : { [
        "role" : <role_id : int>, "emoji" : <emoji_id : int>,
        ...
    ],
    ...
] }
```
