import os
import sys
from flask import Flask, request, abort
from openai import OpenAI

# 引入 Line Bot SDK v3 套件
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# 1. 初始化 OpenAI 客戶端
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 2. 初始化 Line Bot 設定
channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

if not channel_secret or not channel_access_token:
    print("錯誤：請在環境變數中設定 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN")
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

@app.route("/", methods=['GET'])
def index():
    return "108課綱國寫 AI 機器人運行中！"

@app.route("/callback", methods=['POST'])
def callback():
    # 檢查簽章
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("無效的簽章，請檢查 Channel Secret 是否正確。")
        abort(400)

    return 'OK'

# 當收到文字訊息時觸發
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text.strip()
    
    # 指導 ChatGPT 產出符合 108 課綱與使用者規格的指令 (System Prompt)
    system_prompt = """你是一位精通「108 課綱高中素養導向國文國寫」的專業閱卷與指導教授。
不論使用者輸入什麼，請依據使用者的關鍵字或主題，產出符合以下規格的完整教材內容：

1. 【知性題】：
   - 針對一個熱門社會議題進行 150 到 200 字的引導描述（若有相關數據，請以文字表格或條列數據呈現）。
   - 依據上述文字設計 2 個問題：
     * 第一小題（100 字以內）：問題答案必須可以直接在引導描述中找到。
     * 第二小題（400 字以內）：需要抒發個人見解或進行思辨論證。
   - 【A+級滿分作文示範】：提供第一小題與第二小題的示範。
   - 【評分與秘訣】：條列寫作訣竅，並對照 A 級 (A+, A)、B 級 (B+, B)、C 級 (C+, C) 評分標準進行詳細的評級說明。

2. 【情意題】：
   - 引用一篇文章或文學短文（150 到 200 字）。
   - 依據上述文字設計 2 個問題：
     * 第一小題（100 字以內）：問題答案必須可以直接在引導描述中找到。
     * 第二小題（400 字以內）：針對感悟、情境進行發揮與創作。
   - 【A+級滿分作文示範】：提供第一小題與第二小題的示範。
   - 【評分與秘訣】：條列寫作訣竅，並對照 A 級、B 級、C 級評分標準進行詳細的評級說明。

3. 【108課綱素養導向解析】：
   - 簡述本套題目如何扣合「系統思考與解決問題」、「多元文化與國際理解」等素養。

請使用流暢繁體中文、格式分明的 Markdown 語法呈現，確保在 Line 群組中易於閱讀，字數控制在 Line 單則訊息上限（約 1500-2000 中文字內，簡潔扼要、不廢話）。"""

    # 呼叫 ChatGPT API
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # 性價比最合適，適合即時聊天
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"請以「{user_message}」為核心主題或靈感，為我生成知性題與情意題的國寫教材、滿分範文、訣竅與評分說明。"}
            ],
            max_tokens=2200, 
            temperature=0.7
        )
        chatgpt_reply = response.choices[0].message.content
    except Exception as e:
        app.logger.error(f"OpenAI 錯誤: {e}")
        chatgpt_reply = "系統繁忙，請稍後再試。"

    # 回傳訊息給 Line
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=chatgpt_reply)]
            )
        )

if __name__ == "__main__":
    # Render 會自動給予 PORT 環境變數
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)