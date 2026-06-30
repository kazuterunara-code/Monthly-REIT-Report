#!/usr/bin/env python3
"""
Gmail OAuth 認証の初回セットアップスクリプト
─────────────────────────────────────────────
このスクリプトはローカルで一度だけ実行します。
実行するとブラウザが開き、Google アカウントで認証が完了すると
token.json が生成されます。

その後、画面に表示される2つの Base64 文字列を
GitHub Secrets に登録してください。

事前準備:
  1. Google Cloud Console でプロジェクトを作成
  2. 「Gmail API」を有効化
  3. OAuth 同意画面を設定（External / テスト）
  4. OAuth クライアント ID を作成（デスクトップアプリ）
  5. credentials.json をダウンロードしてこのスクリプトと同じ場所に配置

実行方法:
  pip install google-auth-oauthlib
  python scripts/setup_gmail_auth.py
"""

import base64
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ google-auth-oauthlib が見つかりません。")
    print("   pip install google-auth-oauthlib を実行してください。")
    sys.exit(1)

SCOPES       = ["https://www.googleapis.com/auth/gmail.compose"]
CREDS_FILE   = "credentials.json"
TOKEN_FILE   = "token.json"


def main():
    import os
    if not os.path.exists(CREDS_FILE):
        print(f"❌ {CREDS_FILE} が見つかりません。")
        print("   Google Cloud Console からダウンロードして、")
        print("   このスクリプトと同じディレクトリに置いてください。")
        sys.exit(1)

    print("=" * 60)
    print("Gmail OAuth 認証セットアップ")
    print("=" * 60)
    print("\nブラウザが開きます。Google アカウントでログインして")
    print("「許可」をクリックしてください...\n")

    flow  = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print(f"✅ {TOKEN_FILE} を生成しました\n")

    # GitHub Secrets 用に Base64 エンコード
    with open(TOKEN_FILE, "rb") as f:
        token_b64 = base64.b64encode(f.read()).decode()
    with open(CREDS_FILE, "rb") as f:
        creds_b64 = base64.b64encode(f.read()).decode()

    print("=" * 60)
    print("以下の値を GitHub Secrets に登録してください")
    print("登録先: リポジトリ → Settings → Secrets and variables → Actions")
    print("=" * 60)

    print("\n【Secret名: GMAIL_TOKEN】")
    print("─" * 40)
    print(token_b64)

    print("\n【Secret名: GMAIL_CREDENTIALS】")
    print("─" * 40)
    print(creds_b64)

    print("\n" + "=" * 60)
    print("✅ セットアップ完了！")
    print("   上記2つの値を GitHub Secrets に登録すれば")
    print("   GitHub Actions からの Gmail アクセスが有効になります。")
    print("=" * 60)

    print("\n⚠️  注意: credentials.json と token.json は")
    print("   絶対に Git にコミットしないでください。")
    print("   .gitignore に追加済みであることを確認してください。")


if __name__ == "__main__":
    main()
