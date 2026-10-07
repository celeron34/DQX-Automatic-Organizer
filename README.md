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
