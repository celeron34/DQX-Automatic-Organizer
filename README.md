# DQX Automatic Organizer

DQXの防衛軍周回募集とパーティ編成を支援するDiscord Botです。1つのリポジトリに3つの独立したBotプロセスを置き、それぞれのBotトークンで起動します。

| Bot | 起動ファイル | 役割 |
|---|---|---|
| スケジュール | `schedule_bot.py` | 公式広場をスクレイピングし、編成Botへ予定を送信 |
| 編成 | `main.py` | 募集、参加受付、イベント進行、パーティ編成 |
| ロール | `role_bot.py` | メンバー用ロール選択パネルの投稿とボタン操作 |

## セットアップ

Python 3.10以降を用意し、依存パッケージをインストールします。

```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install py-cord selenium
```

`IDs.json` にDiscordサーバー、チャンネル、ロール、絵文字のIDを設定します。従来の設定形式を使います。設定例は `example_config.json` を参照してください。`IDs.json` とBotトークンをGitへコミットしないでください。

各プロセスに別々のトークンを環境変数で渡します。

```sh
export SCHEDULE_BOT_TOKEN="スケジュールBotのトークン"
export FORMATION_BOT_TOKEN="編成Botのトークン"
export ROLE_BOT_TOKEN="ロールBotのトークン"
export SCHEDULE_SYNC_CHANNEL_ID="専用チャンネルのID"
export FORMATION_BOT_USER_ID="編成BotのユーザーID"
```

編成Botだけは移行期間中 `token.json` の `{"token": "..."}` も読み込みます。スケジュールBotとロールBotは専用の環境変数が必要です。

専用チャンネルを作成し、スケジュールBotにはメッセージ送信・メッセージ閲覧権限、編成Botにはメッセージ送信・履歴閲覧・添付ファイル閲覧権限を付与します。両Botに同じ `SCHEDULE_SYNC_CHANNEL_ID` を設定し、スケジュールBotには許可する依頼元である編成Botの `FORMATION_BOT_USER_ID` を設定します。チャンネルは他のメンバーから見えないようにします。

## 起動

```sh
python main.py
python schedule_bot.py /path/to/chrome /path/to/chromedriver
python role_bot.py
```

スケジュール取得は自動では開始しません。人はスケジュールBotの `/f-timetable` または `/f-schedule-refresh` を実行できます。編成Botの `/f-schedule-request` を実行すると、専用チャンネル経由でスケジュールBotへ取得を依頼します。スケジュールBotは依頼を検証してスクレイピングし、取得結果をJSON添付メッセージとして投稿します。編成Botが受信してイベントを同期します。ブラウザーとChromeDriverのパスは省略できます。必要なら `CHROME_BINARY` と `CHROMEDRIVER` 環境変数でも指定できます。ロールBotは起動時にロールパネルを投稿し、`/f-role-panel-refresh` で再生成します。

スケジュールBotが予定データの送り手で、編成Botが受け取ったデータからイベントを生成・同期します。Discordのスラッシュコマンドは人がBotごとに実行する操作なので、Botが別Botのスラッシュコマンドを直接呼び出す形にはできません。代わりに専用チャンネルのメッセージをBot間の受け渡しに使います。同じ予定を再送しても、イベントの実行状態は維持されます。ロールBotはこの連携に関与しません。

## Discord Bot設定

各Botを対象サーバーに招待し、担当機能に必要な権限を付与します。編成Botはメンバー、メッセージ内容、リアクションのIntentを有効にしてください。スケジュールBotはメッセージ内容Intentを有効にし、Bot間依頼を専用チャンネルで受信できるようにします。ロールBotはメンバーIntentとロール管理権限が必要で、対象ロールより上にBotロールを配置します。

## テスト

```sh
python -m unittest discover -s test -v
python -m compileall -q .
```

スクレイピングの変換やBot間の予定データ形式のテストは、Discord接続や実ページへのアクセスなしで実行できます。
