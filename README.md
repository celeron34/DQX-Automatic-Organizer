# DQX Automatic Organizer

DQXの防衛軍周回募集とパーティ編成を支援するDiscord Botです。公式広場のタイムテーブルを取得し、全兵団の予定に合わせて参加募集、パーティ編成、参加者管理を行います。

## できること

- 公式広場のタイムテーブルから防衛軍の予定を取得
- 募集メッセージと参加リアクションの受付
- 参加者を高速周回向け・ライトパーティ向けに編成
- パーティごとのスレッド作成、参加申請、途中参加・離脱の管理
- CSV形式で参加者データやメンバー情報を出力
- イベントごとに状態を分け、複数の予定を並行して進行

## イベントの進行

各イベントは独立した `EventInstance` として管理されます。現在のフェーズ境界は次のとおりです。

| 時刻 | 処理 |
|---|---|
| 開始30分前 | 募集メッセージを投稿し、参加受付を開始 |
| 開始15分前 | パーティ編成までのリマインダーを投稿 |
| 開始10分前 | 参加者を集計してパーティを編成 |
| 開始時刻 | Botのステータスを更新 |
| 開始60分後 | 最終参加人数を記録し、タイムテーブルを更新 |

イベント状態は募集メッセージ、参加者一覧、パーティ一覧などを含みます。イベントが重なっても、各イベントの状態は混ざりません。処理は1分ごとに実行されます。

## セットアップ

### 動作環境

- Python 3.10以降
- Discord BotとPycord
- Selenium
- ChromeまたはChromiumと対応するChromeDriver

### インストール

```sh
git clone https://github.com/celeron34/DQX-Automatic-Organizer.git
cd DQX-Automatic-Organizer

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

python -m pip install py-cord selenium
```

### DiscordとBotの設定

起動時に次の2ファイルを読み込みます。どちらも機密情報やサーバー固有IDを含むため、Gitへコミットしないでください。

`token.json`:

```json
{
  "token": "Discord Bot Token"
}
```

`IDs.json`:

```json
[
  {
    "guildID": 123456789012345678,
    "channels": {
      "party": 123456789012345678,
      "party-beta": 123456789012345678,
      "party-log": 123456789012345678,
      "develop": 123456789012345678,
      "command": 123456789012345678,
      "recruit-log": 123456789012345678
    },
    "emojis": {
      "recruiting": 123456789012345678,
      "fullparty": 123456789012345678,
      "lightparty": 123456789012345678
    },
    "raidRoles": {
      "ロール名": {
        "role": 123456789012345678,
        "emoji": 123456789012345678,
        "count": 1
      }
    },
    "roles": {
      "member": 123456789012345678,
      "priority": 123456789012345678,
      "staticPriority": 123456789012345678,
      "master": 123456789012345678,
      "liteParty": 123456789012345678
    },
    "settingRoles": [
      {
        "name": "ロール名",
        "role": 123456789012345678,
        "emoji": 123456789012345678
      }
    ]
  }
]
```

各数値は、対象Discordサーバーのチャンネル・ロール・絵文字IDに置き換えてください。現在の起動処理は `IDs.json` の先頭のサーバー設定を使います。ロール設定で `raidRoles` に登録する `count` は、そのロールの編成枠数です。

Botにはメンバー情報・メッセージ内容・リアクションのIntentを有効にし、対象チャンネルでメッセージ送信、履歴閲覧、リアクション、スレッド作成・参加者管理ができる権限を付与してください。メンバーにロールを付与する機能を使う場合、Botのロールを対象ロールより上に配置します。

現行の起動処理が読む設定ファイルは `IDs.json` と `token.json` です。`example_config.json` は現在の起動処理では読み込まれません。

### 起動

`main.py` はブラウザー実行ファイルとChromeDriverのパスをコマンドライン引数で受け取ります。

```sh
python main.py /path/to/chrome /path/to/chromedriver
```

Selenium ManagerでChromeDriverを解決する場合は、2つ目の引数に空文字を渡します。

```sh
python main.py /path/to/chrome ""
```

Windowsでは各パスを引用符で囲んでください。相対パスで指定する募集文やログの保存先もあるため、リポジトリのルートディレクトリから起動します。

## Discordコマンド

| コマンド | 内容 |
|---|---|
| `/f-formation` | 現在時刻から31分後の割り込み予定を追加 |
| `/f-timetable` | タイムテーブルを再取得 |
| `/f-restart` | Botを再起動。イベント開始が近い場合は再起動時刻を設定 |
| `/f-stop` | Botを停止 |
| `/f-rand` | 指定範囲の整数をランダムに返す |
| `/f-get-participant-data` | 参加データCSVを出力 |
| `/f-get-participant-name` | メンバーIDと表示名のCSVを出力 |
| `/f-get-participant-role` | メンバーIDとロールのCSVを出力 |
| `/f-fetch` | ギルド・チャンネル・ロール設定を再読み込み |

スラッシュコマンドの開発用ギルドIDは `main.py` の `debug_guilds` に設定されています。別のサーバーでコマンドを使う場合は、利用環境に合わせて変更してください。

## タイムテーブルのスクレイピング

`dqx_ise.py` の `getTable(browser_path=None, driver_path=None)` は、公式広場の防衛軍タイムテーブルを読み取り、`DefenseScheduleEntry` のリストを返します。

| フィールド | 型 | 内容 |
|---|---|---|
| `datetime` | `datetime` | 開催日時 |
| `force_id` | `int` | ページから取得した兵団ID |
| `is_all_forces` | `bool` | 現在ページに掲載された兵団一覧にないIDかどうか |

兵団IDはページ上のリンクから実行時に取得します。固定の兵団名リストには依存しません。現行のBotは、取得結果のうち `is_all_forces` が真の予定をイベント時刻として採用します。

```python
from dqx_ise import getTable

for entry in getTable("/path/to/chrome", "/path/to/chromedriver"):
    print(entry.datetime, entry.force_id, entry.is_all_forces)
```

スクレイピングと変換は次の関数に分かれています。

- `get_file_names(parent, xpath, attribute="src")`: XPathに一致する要素から指定属性のファイル名を取得。URLデコードを行い、クエリ文字列とフラグメントは除外します。
- `get_force_ids(parent)`: 現在のページにある兵団IDを取得します。
- `build_schedule_entries(table_png_names, start_at, force_ids)`: アイコン名と開始日時、現在の兵団ID一覧から予定データを作ります。

Seleniumの読み込みは `getTable` の呼び出し時だけ行われます。そのため、変換関数やユニットテストはブラウザーを起動せずに実行できます。

## 募集文とログ

募集文・画像は次のディレクトリに置きます。

```text
guilds/<guild_id>/recruitingMessage/
├── 1.txt
├── 1-1.png
├── 2.md
└── 2.png
```

番号順に読み込まれます。テキストには `{hour}`（開催時刻）と `{count}`（募集人数）の置換文字列を使えます。旧フォルダー名を使っている既存環境も互換用に読み込みます。新しい環境では上記の正しいフォルダー名を使ってください。

参加ログは `reactionLog/`、一時ファイルは `cache/` に保存されます。これらのデータや `IDs.json`、`token.json` はリポジトリに含めないでください。

## テスト

```sh
python -m unittest discover -s test -v
python -m compileall -q dqx_ise.py main.py test
```

ユニットテストはBotの起動、Discord接続、実際のタイムテーブルへのアクセスを必要としません。

## 主なファイル

| ファイル | 役割 |
|---|---|
| `main.py` | Bot起動、Discordイベント受付、各機能の接続 |
| `event_definition.py` | イベント設定・インスタンスとフェーズ判定 |
| `event_runner.py` | イベントごとの募集・編成・終了処理 |
| `guild.py` | Discordサーバーごとのチャンネル・ロール・イベント一覧 |
| `party.py` | パーティと参加者の状態・操作 |
| `views.py` | DiscordのボタンやView |
| `commands.py` | スラッシュコマンド登録 |
| `support_utils.py` | 共通処理、募集文、ファイル読み込み |
| `dqx_ise.py` | 防衛軍タイムテーブルの取得と変換 |
| `formation.py` | パーティ編成アルゴリズム |
| `test/` | ユニットテスト |
