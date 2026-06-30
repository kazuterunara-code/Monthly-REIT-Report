# セットアップ手順

このリポジトリを GitHub Actions で自動実行するための手順です。  
完了すると **毎月1日 10:00 JST** にレポートが自動生成され、Gmail 下書きに保存されます。

---

## 必要なもの（取得先）

| 必要なもの | 取得先 | 費用 |
|---|---|---|
| GitHub アカウント | github.com | 無料 |
| Anthropic API キー | console.anthropic.com | 従量課金（月数百円程度） |
| Tavily API キー | app.tavily.com | 無料枠 1,000回/月 |
| Google Cloud OAuth | console.cloud.google.com | 無料 |

---

## Step 1: GitHub リポジトリを作成

```bash
# このフォルダを Git リポジトリにして GitHub に push する
cd /path/to/東京REIT指数関連ニュース自動通知

git init
git add .
git commit -m "initial commit"

# GitHub で新しいリポジトリを作成後（例: reit-monitor）
git remote add origin https://github.com/あなたのユーザー名/reit-monitor.git
git push -u origin main
```

---

## Step 2: Anthropic API キーを取得

1. https://console.anthropic.com にアクセス
2. 「API Keys」→「Create Key」でキーを生成
3. 生成されたキー（`sk-ant-...`）をメモ

---

## Step 3: Tavily API キーを取得

1. https://app.tavily.com にアクセスしてサインアップ
2. ダッシュボードに表示される API キー（`tvly-...`）をメモ

---

## Step 4: Google Cloud で Gmail API を有効化

1. https://console.cloud.google.com にアクセス
2. 新しいプロジェクトを作成（例: `reit-monitor`）
3. 左メニュー「API とサービス」→「ライブラリ」→「Gmail API」を検索して**有効化**
4. 「OAuth 同意画面」を設定
   - ユーザーの種類: **外部**
   - アプリ名: 任意（例: REIT Monitor）
   - テストユーザーに `kazuterunara@gmail.com` を追加
5. 「認証情報」→「認証情報を作成」→「OAuth クライアント ID」
   - アプリの種類: **デスクトップアプリ**
   - 名前: 任意
6. `credentials.json` をダウンロードしてこのフォルダのルートに配置

---

## Step 5: Gmail 認証トークンを生成

`credentials.json` をルートに置いた状態で実行：

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# Gmail 認証セットアップ（ブラウザが開きます）
python scripts/setup_gmail_auth.py
```

ブラウザで Google アカウントにログインして「許可」をクリックすると、  
ターミナルに **GMAIL_TOKEN** と **GMAIL_CREDENTIALS** の Base64 文字列が表示されます。

---

## Step 6: GitHub Secrets に登録

GitHub リポジトリの **Settings → Secrets and variables → Actions → New repository secret** で以下を登録：

| Secret 名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | Step 2 で取得したキー |
| `TAVILY_API_KEY` | Step 3 で取得したキー |
| `GMAIL_TOKEN` | Step 5 で表示された GMAIL_TOKEN の Base64 文字列 |
| `GMAIL_CREDENTIALS` | Step 5 で表示された GMAIL_CREDENTIALS の Base64 文字列 |

---

## Step 7: 動作確認（手動実行）

GitHub リポジトリの **Actions タブ** を開き、  
「月次 REIT レポート自動生成」→「Run workflow」で手動実行できます。

ログを確認して `✅ Gmail 下書き作成完了` が表示されれば成功です。

---

## スケジュール

`.github/workflows/monthly_report.yml` の cron 設定：

```yaml
- cron: '0 1 1 * *'   # 毎月1日 01:00 UTC = 10:00 JST
```

変更したい場合は cron 式を編集してください。

---

## トラブルシューティング

**「token.json が期限切れ」エラーが出る場合**  
→ Step 5 を再実行して `GMAIL_TOKEN` Secret を更新してください。

**「Tavily 検索エラー」が出る場合**  
→ 無料枠（1,000回/月）を超えた可能性があります。Tavily ダッシュボードで使用量を確認してください。

**「ANTHROPIC_API_KEY が無効」エラー**  
→ Anthropic Console でキーの有効期限・残高を確認してください。
