#!/usr/bin/env python3
"""
月次 東京REIT関連マーケット情報 自動生成スクリプト
GitHub Actions で毎月1日に自動実行されます。

必要な環境変数:
  ANTHROPIC_API_KEY  : Anthropic API キー
  TAVILY_API_KEY     : Tavily Search API キー

必要なファイル（GitHub Secrets から復元）:
  credentials.json   : Google Cloud OAuth クライアント情報
  token.json         : Gmail OAuth アクセストークン
"""

import base64
import os
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tavily import TavilyClient

# ── 定数 ──────────────────────────────────────────────────────────────────────
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
TO_EMAIL     = "kazuterunara@gmail.com"
REPORT_DIR   = "reports"
MODEL        = "claude-sonnet-4-6"


# ── Gmail ─────────────────────────────────────────────────────────────────────
def get_gmail_service():
    """Gmail API サービスを取得（トークン自動更新付き）"""
    creds = Credentials.from_authorized_user_file("token.json", GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def create_draft(service, subject: str, html_body: str, to: str) -> str:
    """Gmail 下書きを作成してドラフトIDを返す"""
    msg = MIMEMultipart("alternative")
    msg["to"]      = to
    msg["subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    raw   = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return draft["id"]


# ── ツール実装 ─────────────────────────────────────────────────────────────────
def do_web_search(query: str, tavily: TavilyClient) -> str:
    """Tavily でウェブ検索し、整形済みテキストを返す"""
    try:
        res   = tavily.search(query=query, search_depth="advanced", max_results=5)
        items = []
        for r in res.get("results", []):
            items.append(
                f"【{r.get('title', '')}】\n"
                f"URL: {r.get('url', '')}\n"
                f"{r.get('content', '')[:600]}"
            )
        return "\n\n---\n\n".join(items) if items else "検索結果なし"
    except Exception as e:
        return f"検索エラー: {e}"


def do_fetch_url(url: str) -> str:
    """URL のページ本文を取得してテキストを返す（先頭3000文字）"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except Exception as e:
        return f"取得エラー: {e}"


# ── Claude ツール定義 ──────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "web_search",
        "description": "日本語ウェブ検索を実行して最新情報を取得する",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ（日本語）"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": "指定 URL のページ本文テキストを取得する",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "取得する URL"}
            },
            "required": ["url"],
        },
    },
]


# ── Claude エージェントループ ───────────────────────────────────────────────────
def run_agent(client: anthropic.Anthropic, tavily: TavilyClient, now: datetime) -> str:
    """
    Claude + Tavily で調査・HTMLレポート生成を行い、メール本文 HTML を返す。
    最大 25 ターンのエージェントループで tool_use を処理する。
    """
    ym = f"{now.year}年{now.month}月"

    system = (
        f"あなたは不動産・金融市場の月次レポートを自動作成するアナリストです。"
        f"今日は {now.strftime('%Y年%m月%d日')} です。"
        f"web_search / fetch_url ツールを必要なだけ使って正確な最新情報を収集し、"
        f"最終的に HTML メール本文を出力してください。"
        f"2ヶ月以上前の情報を最新として扱わないこと。"
    )

    user = f"""以下の4項目を調査し、HTML 形式の月次レポートメール本文を作成してください。

【調査項目】

1. 日銀 金融政策決定会合（{ym}）
   - 「日本銀行 金融政策決定会合 結果 {ym}」で検索
   - 「日銀 政策金利 決定 {ym}」で検索
   - 把握：会合日・決定内容・政策金利・声明要点・次回会合日

2. マンション賃料インデックス 東京23区（最新）
   - 「三井住友トラスト基礎研究所 マンション賃料インデックス {now.year}年」で検索
   - https://www.smtri.jp/market/mansion/ を参照
   - 把握：公表日・対象期間・前期比・前年同期比・タイプ別（シングル・コンパクト・ファミリー）

3. 東証REIT指数 直近動向（{ym}）
   - 「東証REIT指数 動向 {ym}」「J-REIT 市場動向 {ym}」で検索
   - 2〜3 件の記事から指数水準・利回り・月間動向・見通しをまとめる

4. イオン大宮（日進駅）周辺の地価（さいたま市北区）
   - イオン大宮の最寄り駅は JR 川越線「日進駅」（さいたま市北区）
   - 「日進駅 さいたま市 公示地価 基準地価 {now.year}年」で検索
   - 「さいたま市 大宮 地価 {ym}」で検索
   - 把握：日進駅周辺の公示地価・基準地価（前年比）、大宮区の商業地・住宅地トレンド、
           日進駅エリアの注目度（副都心位置づけ・再開発・大宮駅との距離感）

【HTML 出力要件】
- <body> タグの内側のみ出力（DOCTYPE・html・head タグは不要）
- スタイルはインライン CSS で記述
- 4 セクションそれぞれに見出し・テーブル・要点を含める
- 最後に 4 項目のまとめ表を追加
- フッターに「本レポートは GitHub Actions により自動作成されました（{now.strftime('%Y年%m月%d日')}）」
- 情報取得できなかった項目は「情報取得できず」と明記"""

    messages = [{"role": "user", "content": user}]

    for turn in range(25):
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        # ── 完了 ──
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    return block.text
            return "<p>レポート生成に失敗しました。</p>"

        # ── ツール呼び出し ──
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "web_search":
                    query  = block.input["query"]
                    print(f"  🔍 検索: {query}")
                    result = do_web_search(query, tavily)
                elif block.name == "fetch_url":
                    url    = block.input["url"]
                    print(f"  🌐 取得: {url}")
                    result = do_fetch_url(url)
                else:
                    result = f"不明なツール: {block.name}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})

    return "<p>最大反復回数に達しました。レポートを生成できませんでした。</p>"


# ── エントリポイント ────────────────────────────────────────────────────────────
def main():
    now = datetime.now()
    print(f"=== 月次 REIT レポート生成開始: {now.strftime('%Y-%m-%d %H:%M')} ===\n")

    # クライアント初期化
    claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    gmail  = get_gmail_service()

    # Claude エージェントで調査・HTML 生成
    print("📡 調査・レポート生成中（Claude + Tavily）...")
    html_body = run_agent(claude, tavily, now)

    # Gmail 下書き作成
    subject  = f"【月次】東京REIT関連マーケット情報 {now.year}年{now.month}月"
    draft_id = create_draft(gmail, subject, html_body, TO_EMAIL)
    print(f"\n✅ Gmail 下書き作成完了 (ID: {draft_id})")

    # Markdown 保存（GitHub Actions アーティファクト用）
    os.makedirs(REPORT_DIR, exist_ok=True)
    md_path = f"{REPORT_DIR}/report_{now.strftime('%Y-%m')}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 月次 REIT レポート {now.strftime('%Y年%m月')}\n\n")
        f.write(f"生成日時: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(html_body)
    print(f"✅ Markdown 保存: {md_path}")

    print("\n=== 完了 ===")


if __name__ == "__main__":
    main()
