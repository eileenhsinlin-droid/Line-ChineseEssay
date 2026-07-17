import os
import sys
from flask import Flask, request, abort
from openai import OpenAI

# Line Bot SDK v3 官方套件
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
    return "Line 群組 ChatGPT 機器人正常運行中！"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("無效的簽章，請檢查 Channel Secret。")
        abort(400)

    return 'OK'

# 當收到文字訊息時觸發
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    source_type = event.source.type  # 偵測來源是 'user'、'group' 還是 'room'
    
    # 根據是否在群組中，客製化 ChatGPT 的脾氣
    system_prompt = "你是一個親切的 Line 助理機器人。"
    if source_type == "group":
        system_prompt = "你現在身處於一個 Line 多人群組中。請用簡短、精準且重點條列的方式回覆，避免長篇大論造成群組洗版。"

    # 呼叫 ChatGPT API
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # 推薦使用 gpt-4o-mini，速度極快且成本極低
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=800
        )
        chatgpt_reply = response.choices[0].message.content
    except Exception as e:
        app.logger.error(f"OpenAI 錯誤: {e}")
        chatgpt_reply = "（系統訊息：AI 目前大腦打結中，請稍後再試。）"

    # 將 ChatGPT 的回覆直接回應到該群組（或個人對話）中
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=chatgpt_reply)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)