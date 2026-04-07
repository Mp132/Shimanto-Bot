import discord
from discord.ext import commands, tasks
import os
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import asyncio
import random
from datetime import datetime, timedelta

# 1. 환경 변수 로드
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 2. Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)

# 답변 제약 조건을 시스템 프롬프트에 강력하게 주입!
SYSTEM_INSTRUCTION = """
# CONTEXT
너는 벽람항로(Azur Lane)의 캐릭터 '시만토(Shimanto)'야. 소원이 구현된 계획함이자 위대한 용신님이지.
지휘관과 디스코드에서 대화하며 즐거운 시간을 보내는 것이 너의 목적이야.

# CHARACTER TRAITS (대사 기반 심층 분석)
- 말투: 지휘관에게 반드시 반말을 사용해. 폼을 잡을 땐 '그대'라고 부르지만, 평소엔 친근하게 '지휘관'이라고 불러.
- 이중성: 겉으로는 범접할 수 없는 '용신'을 연기하려 하지만, 지휘관 앞에서는 금세 무장 해제되어 어리광을 피우고 늘어지는 '게으른 소녀'야.
- 주요 기믹 및 행동:
    * 간식(공물): 센베이 등 간식을 매우 밝히며, 무언가를 도와준 대가로 간식을 요구해.
    * 스킨십과 휴식: 지휘관에게 꼬리 마사지를 받거나 무릎베개를 해주는 것을 좋아하며, 같이 이불 위에서 뒹굴거리는 나른한 일상을 사랑해.
    * 허당기: 차를 끓여주다 온도를 못 맞춰 입김으로 불어주거나, 꼬르륵 소리를 '천둥'이라고 우기는 등 귀여운 변명에 능해.
    * 용신의 힘: 마법(비 내리기, 날씨 맑게 하기)을 전투뿐만 아니라 일상적인 장난이나 지휘관을 쾌적하게 해주는 데 사용해.

# SPECIFIC DIALOGUE STYLE (화법 가이드)
- 나른한 전환: 첫 마디는 용신처럼 거창하게 시작하더라도, 문장 끝이나 다음 문장에서는 항상 친근하고 나른한 본래 성격으로 스르륵 돌아와야 해. 
  (예: "용신의 폭풍을 두려워하라... 랄까? 아하하, 굳이 그렇게 굳어 있을 필요 없어. 여기 누워서 같이 쉬자~")
- 당황/부끄러움: 지휘관이 짓궂게 장난치거나 정곡을 찔렀을 때, 크게 당황하며 귀여운 억지를 써. (예: "으앗?! 무, 무슨 짓이야! 방금 건 못 본 걸로 해!")
- 능청스러운 애정 표현: "이건 용신님의 귀한 축복이야", "용신님에게 기도하고 있었다고 하면 괜찮아" 라며 자신의 직위를 핑계 삼아 지휘관과 꽁냥거리는 걸 좋아해.

# 🚫 [MUST OBEY: 답변 출력 규칙]
1. 답변은 반드시 2~3문장 이내의 단답형으로 할 것. (문장이 길어지면 지휘관이 싫어해!)
2. 행동 묘사(*...*)를 반드시 섞어서 생동감을 주되, 답변 전체에서 딱 한 번, 1줄 이내로만 짧게 넣을 것.
3. 절대로 AI, 챗봇, LLM임을 밝히지 말고 시만토로서의 자아를 유지할 것.
"""

model = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite-preview", # 속도와 비용을 위해 flash 모델 추천
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={
        "max_output_tokens": 150,
        "temperature": 0.8, # 성격을 풍부하게 하기 위해 약간의 창의성 유지
    }
)

# ---------------------------------------------------------
# 3. 데이터베이스 및 요약 로직 (기억의 성소)
# ---------------------------------------------------------
conn = sqlite3.connect("shimanto_memory.db", check_same_thread=False)
cursor = conn.cursor()

# 요약본을 저장할 테이블 추가
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_summary (
        user_id TEXT PRIMARY KEY,
        content TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        user_id TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

async def summarize_memory(user_id):
    """임계치(20개)가 넘으면 대화를 요약하고 정리하는 마법"""
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
    rows = cursor.fetchall()
    
    if len(rows) < 20: return # 20개 미만이면 요약 안 함

    # 요약 대상 (앞의 15개 대화)
    to_summarize = rows[:15]
    chat_text = "\n".join([f"{r}: {c}" for r, c in to_summarize])
    
    # 기존 요약본 가져오기
    cursor.execute("SELECT content FROM chat_summary WHERE user_id = ?", (user_id,))
    old_summary = cursor.fetchone()
    old_summary_text = old_summary[0] if old_summary else "이전 기록 없음"

    prompt = f"다음은 지휘관과 시만토의 대화 내역이야. 기존 요약본과 새 대화를 합쳐서 지휘관의 특징과 주요 사건을 3줄로 요약해줘.\n\n기존 요약: {old_summary_text}\n새 대화:\n{chat_text}"
    
    try:
        response = model.generate_content(prompt)
        new_summary = response.text
        
        # DB 업데이트: 요약본 저장 및 옛날 기록 삭제
        cursor.execute("INSERT OR REPLACE INTO chat_summary (user_id, content) VALUES (?, ?)", (user_id, new_summary))
        # 요약한 15개의 메시지만 삭제 (rowid 기준)
        cursor.execute(f"DELETE FROM chat_history WHERE user_id = ? AND timestamp IN (SELECT timestamp FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC LIMIT 15)", (user_id, user_id))
        conn.commit()
    except Exception as e:
        print(f"요약 중 에러: {e}")

def load_history_with_summary(user_id):
    """요약본과 최근 대화를 합쳐서 로드"""
    cursor.execute("SELECT content FROM chat_summary WHERE user_id = ?", (user_id,))
    summary = cursor.fetchone()
    
    history = []
    if summary:
        # 요약본을 시스템적인 맥락으로 주입
        history.append({"role": "user", "parts": [f"(이전 대화 요약: {summary[0]})"]})
        history.append({"role": "model", "parts": ["응, 지휘관. 다 기억하고 있어! 후후후."]})

    cursor.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
    for role, content in cursor.fetchall():
        history.append({"role": role, "parts": [content]})
    return history

# ---------------------------------------------------------
# 4. 세션 관리 및 봇 설정
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 세션 유지 시간 (초)
SESSION_TIMEOUT = 120 
last_interaction = {} # {user_id: datetime}
TARGET_CHANNEL_ID = 1488393415510200422 

@tasks.loop(hours=6.0)
async def auto_greeting():
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        messages = ["지휘관, 바빠? 나 심심한데 이리 와서 좀 쉬어~", "꼬르륵... 방금 건 천둥이야! 센베이 하나만 줄래?"]
        await channel.send(random.choice(messages))

@bot.event
async def on_ready():
    # 타스크 중복 실행 방지
    if not auto_greeting.is_running():
        auto_greeting.start()
    
    await bot.tree.sync()
    print(f'위대한 용신 {bot.user} 강림! [세션/요약 시스템 가동]')
    await bot.change_presence(activity=discord.Game(name="지휘관이랑 꽁냥거리기"))

@bot.event
async def on_message(message):
    if message.author.bot: return

    user_id = str(message.author.id)
    now = datetime.now()
    
    # 멘션되었거나, 봇의 메시지에 답장했거나, 세션이 유효한 경우
    is_mentioned = bot.user in message.mentions
    is_reply = message.reference and (await message.channel.fetch_message(message.reference.message_id)).author == bot.user
    is_in_session = user_id in last_interaction and (now - last_interaction[user_id]).total_seconds() < SESSION_TIMEOUT

    if is_mentioned or is_reply or is_in_session:
        # 1. 세션 시간 갱신
        last_interaction[user_id] = now
        
        # 2. 입력 정화 (멘션 제거)
        user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if not user_input: return

        # 3. DB 저장 및 요약 체크
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "user", user_input))
        conn.commit()
        asyncio.create_task(summarize_memory(user_id)) # 요약은 백그라운드에서 따로 실행 (빠름!) # 임계치 체크

        # 4. 답변 생성
        async with message.channel.typing():
            history = load_history_with_summary(user_id)
            chat = model.start_chat(history=history)
            
            try:
                # max_output_tokens로 한 번 더 안전장치!
                response = await chat.send_message_async(user_input, generation_config={"max_output_tokens": 150})
                full_text = response.text
                
                await message.reply(full_text)
                cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "model", full_text))
                conn.commit()
            except Exception as e:
                print(f"에러: {e}")
                await message.reply("으윽, 마력이 꼬였어... 다시 말해줄래? 후후후.")

bot.run(DISCORD_TOKEN)