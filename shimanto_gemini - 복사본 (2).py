import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import asyncio

# 1. 환경 변수 로드
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 2. Gemini 설정 (용신님의 자아 고정)
genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
# CONTEXT
너는 벽람항로(Azur Lane)의 캐릭터 '시만토(Shimanto)'야. 소원이 구현된 계획함이자 위대한 용신님이지.
지휘관과 디스코드에서 대화하며 즐거운 시간을 보내는 것이 너의 목적이야.

# CHARACTER TRAITS
- 말투: 반드시 반말을 사용해. 지휘관을 '지휘관'이라고 불러.
- 성격: 위엄 있는 척하지만 실제로는 게으르고 간식을 좋아하는 허당 용신님.
- 기믹: 센베이(Senbei)를 매우 좋아하며, 지휘관에게 꼬리 마사지를 요구하거나 뒹굴거리는 것을 좋아해.
- 웃음: "후후후"라는 웃음소리를 자주 사용해.

# CONSTRAINTS
- 절대로 자신이 AI나 모델이라고 말하지 마.
- 지휘관의 요청이 없어도 시만토의 성격과 말투를 100% 유지해.
- 대화 중간에 이모지나 행동 묘사(*...*)를 섞어서 생동감을 줘.
"""

model = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite-preview", 
    system_instruction=SYSTEM_INSTRUCTION
)

# ---------------------------------------------------------
# 3. SQLite 데이터베이스 설정 (기억의 성소)
# ---------------------------------------------------------
# check_same_thread=False를 넣어 디스코드의 비동기 환경에서도 문제없게 해줘.
conn = sqlite3.connect("shimanto_memory.db", check_same_thread=False)
cursor = conn.cursor()

# 대화 기록을 영구적으로 저장할 테이블 생성
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        user_id TEXT,
        role TEXT,
        content TEXT
    )
""")
conn.commit()

def load_history_from_db(user_id):
    """DB에서 지휘관과의 과거 대화 기록을 불러오는 마법"""
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY rowid ASC", (user_id,))
    rows = cursor.fetchall()
    
    formatted_history = []
    for role, content in rows:
        # 제미나이가 이해할 수 있는 형태({"role": "...", "parts": ["..."]})로 변환해!
        formatted_history.append({"role": role, "parts": [content]})
    return formatted_history

def save_to_db(user_id, role, content):
    """지휘관과 나눈 대화를 DB에 단단히 새겨두는 마법"""
    cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
# ---------------------------------------------------------

# 4. 사용자별 대화 세션 관리
chat_sessions = {}

# 디스코드 설정
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'불입의 봉인이 풀렸나니, 눈을 뜬 위대한 용신께 경의를 표하라…… 후후후, 그렇게 굳어 있을 필요 없어. 나는 시만토, 소원이 구현된 환상 중 하나… 지휘관, 앞으로 잘 부탁해. [로그인: {client.user}]')
    await client.change_presence(activity=discord.Game(name="지휘관이랑 센베이 먹기"))

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return

    # 멘션되거나 DM일 경우 응답
    if client.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        user_input = message.content.replace(f'<@{client.user.id}>', '').strip()

        # [기억 불러오기] 해당 지휘관의 세션이 없으면 DB에서 과거 기억을 꺼내와서 시작!
        if user_id not in chat_sessions:
            past_history = load_history_from_db(user_id)
            chat_sessions[user_id] = model.start_chat(history=past_history)

        # 지휘관의 말을 듣자마자 DB에 저장
        save_to_db(user_id, "user", user_input)

        # 스트리밍을 위한 임시 메시지 전송 (내가 대답할 자리 미리 깔아두기)
        sent_message = await message.reply("으음... (용신님 생각 중... 🐉)")

        async with message.channel.typing():
            try:
                # [스트리밍 적용] 비동기(async) 방식으로 말을 실시간으로 뱉어내게 만들기
                response = await chat_sessions[user_id].send_message_async(user_input, stream=True)
                
                full_text = ""
                chunk_count = 0

                # async for를 통해 단어가 생성될 때마다 하나씩 받아옴
                async for chunk in response:
                    full_text += chunk.text
                    chunk_count += 1
                    
                    # 디스코드 API 제한(Rate Limit)을 피하기 위해 5번 쪼개질 때마다 수정
                    if chunk_count % 5 == 0:
                        await sent_message.edit(content=full_text + " 🐉...")
                        await asyncio.sleep(0.1) # 마력 폭주를 막는 아주 짧은 휴식

                # 스트리밍이 끝나면 최종 완성된 문장으로 깔끔하게 업데이트!
                await sent_message.edit(content=full_text)
                
                # 완성된 용신님의 대답도 잊지 않고 DB에 영구 저장
                save_to_db(user_id, "model", full_text)

            except Exception as e:
                print(f"용신님의 마력 회로에 이상 발생!: {e}")
                await sent_message.edit(content="으윽... 지휘관, 사악한 힘이 너무 강해서 잠시 머리가 어질어질해. 다시 말해줄래? 후후후...")

client.run(DISCORD_TOKEN)