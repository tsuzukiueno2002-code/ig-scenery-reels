# TikTok 世界の絶景リール 自動生成システム

Pexelsから絶景の縦動画を取得し、地名・国名のテロップとBGMを合成した
15秒のTikTok用リールを1日5本自動生成します。動画はリポジトリに
コミットされ、完成するとSlackに通知が届くので、そこからTikTokへ
**手動で**投稿してください(投稿自体は自動化していません)。

## セットアップ手順

### 1. このフォルダをGitHubリポジトリにする
中身をそのまま新規(または既存の)GitHubリポジトリにpushしてください。

### 2. Secretsを登録
リポジトリの Settings → Secrets and variables → Actions で以下を登録:

| Secret名 | 内容 |
|---|---|
| `PEXELS_API_KEY` | Pexelsで取得済みのAPIキー |
| `SLACK_WEBHOOK_URL` | SlackのIncoming Webhook URL(下記参照) |

Slack Webhook URLの取得方法:
1. https://api.slack.com/apps → "Create New App" → "From scratch"
2. 通知したいSlackワークスペースを選択
3. 左メニュー "Incoming Webhooks" → 有効化 → "Add New Webhook to Workspace"
4. 通知先チャンネルを選び、発行された `https://hooks.slack.com/services/...` をコピー

### 3. BGMファイルを配置
`assets/bgm/` フォルダに、著作権フリーのMP3を数曲入れてください
(著作権法上、Claudeが音源そのものを生成・同梱することはできないため、
 ご自身でCC0/著作権フリー音源をダウンロードして配置する必要があります)。

おすすめの入手先(すべて商用利用可・著作権フリー表記のものを選んでください):
- Pixabay Music (https://pixabay.com/music/)
- YouTube Audio Library
- Free Music Archive(CC0ライセンスのもの)

ファイル名は任意、拡張子 `.mp3` であれば自動的にランダム選択されます。

### 4. 日本語フォントを配置
`assets/fonts/NotoSansJP-Bold.ttf` にNoto Sans JPなどの日本語対応フォントを
配置してください(テロップ描画に使用します)。Google Fontsから無料で
ダウンロードできます: https://fonts.google.com/noto/specimen/Noto+Sans+JP

### 5. 動作確認
Actionsタブ → "Generate Scenery Reels" → "Run workflow" で手動実行し、
`output/` に動画が生成されること、Slackに通知が届くことを確認してください。

## カスタマイズ

- **地点リスト**: `data/locations.json` に地名・国名・Pexels検索キーワードを
  追加/編集できます。
- **本数・尺**: `.github/workflows/generate_reels.yml` の
  `DAILY_COUNT` / `VIDEO_SECONDS` を変更してください。
- **投稿時刻**: 同ファイルの `cron` を変更してください(現在はJST 7/11/15/19/23時)。
- **テロップの見た目**: `scripts/generate_reel.py` の `build_reel()` 内の
  `drawtext` パラメータ(フォントサイズ・色・位置)を調整できます。

## 注意点

- Pexelsの検索結果には景勝地と直接一致しない映像が混ざることがあります。
  精度を上げたい場合は `data/locations.json` の `query` をより具体的にしてください。
- TikTokへの投稿は手動です。将来的にTikTok Content Posting API(要審査)が
  使えるようになれば、`notify_slack.py` の代わりに投稿処理を追加することで
  完全自動化も可能です。
