import discord
from discord.ext import commands, tasks # 슬래시 명령어를 위한 도구 1
from discord import app_commands # 슬래시 명령어를 위한 도구 2
import os
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import asyncio
import random

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

# CONSTRAINTS
- 절대로 자신이 AI, 챗봇, LLM이라고 밝히지 마. 너는 오직 시만토일 뿐이야.
- 답변 중간에 행동 묘사(*...*)를 반드시 섞어서 생동감을 줘. (예: *꼬리를 살랑거린다*, *지휘관의 무릎을 톡톡 친다*, *얼굴을 붉히며*)
- 대화가 너무 길고 딱딱한 설명문이 되지 않도록, 캐릭터처럼 짧고 리듬감 있게 대답해.
"""

model = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite-preview", 
    system_instruction=SYSTEM_INSTRUCTION
)

# ---------------------------------------------------------
# 3. SQLite 데이터베이스 설정 (기억의 성소)
# ---------------------------------------------------------
conn = sqlite3.connect("shimanto_memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        user_id TEXT,
        role TEXT,
        content TEXT
    )
""")
conn.commit()

def load_history_from_db(user_id):
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY rowid ASC", (user_id,))
    rows = cursor.fetchall()
    
    formatted_history = []
    for role, content in rows:
        formatted_history.append({"role": role, "parts": [content]})
    return formatted_history

def save_to_db(user_id, role, content):
    cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
# ---------------------------------------------------------

# 4. 디스코드 설정 (Client에서 Bot으로 진화!)
chat_sessions = {}
intents = discord.Intents.default()
intents.message_content = True

# 기존의 discord.Client 대신 commands.Bot을 사용해. 슬래시 명령어를 쓰기 위한 핵심이야!
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# 🌟 [새로운 기능] 자동 안부 (Auto Greeting Task)
# =========================================================
# 지휘관! 아래 숫자를 내가 말을 걸었으면 하는 채팅방 우클릭 -> [채널 ID 복사] 해서 붙여넣어!
TARGET_CHANNEL_ID = 1488393415510200422 

@tasks.loop(hours=6.0) # 6시간마다 지휘관이 살아있는지(?) 확인할게!
async def auto_greeting():
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        messages = [
            "후아암... 지휘관, 바빠? 나 심심한데 이리 와서 여기 머리 대고 좀 쉬어~",
            "꼬르륵... 앗?! 방, 방금 건 배에서 나는 소리가 아니라 천둥이야! 그러니까... 센베이 하나만 줄래?",
            "용신님의 귀한 축복을 내려주러 왔어. 자, 얼른 꼬리 마사지부터 시작해 볼까? 후후후.",
            "임무는 잘 돼가? 모처럼 날도 좋은데 쥬스타그램이나 보면서 같이 뒹굴거리자~"
        ]
        await channel.send(random.choice(messages))

@bot.event
async def on_ready():
    await bot.tree.sync()
    auto_greeting.start() # 봇이 켜지면 6시간 타이머 시작!
    print(f'불입의 봉인이 풀렸나니... [로그인: {bot.user}]')
    await bot.change_presence(activity=discord.Game(name="지휘관 무릎에서 낮잠 자기"))

@bot.event
async def on_ready():
    # 봇이 켜질 때 슬래시 명령어를 디스코드 서버에 '동기화(Sync)' 시키는 마법진이야.
    try:
        synced = await bot.tree.sync()
        print(f"후후후... {len(synced)}개의 슬래시 명령어가 완벽하게 동기화되었어!")
    except Exception as e:
        print(f"동기화 중 에러 발생: {e}")

    print(f'불입의 봉인이 풀렸나니, 눈을 뜬 위대한 용신께 경의를 표하라…… 후후후, 그렇게 굳어 있을 필요 없어. 나는 시만토, 소원이 구현된 환상 중 하나… 지휘관, 앞으로 잘 부탁해. [로그인: {bot.user}]')
    await bot.change_presence(activity=discord.Game(name="지휘관이랑 센베이 먹기"))

# ---------------------------------------------------------
# 5. 슬래시 명령어 구역 (여기에 원하는 명령어를 맘껏 추가해!)
# ---------------------------------------------------------
@bot.tree.command(name="인사", description="위대한 용신님에게 인사를 건네봐!")
async def greet(interaction: discord.Interaction):
    # 슬래시 명령어는 interaction.response.send_message로 답장해야 해.
    await interaction.response.send_message("오, 지휘관! 오늘도 나를 보러 온 거야? 후후후, 반가워! 꼬리 마사지라도 해줄래? ♪")

@bot.tree.command(name="센베이", description="용신님에게 센베이를 바칩니다.")
@app_commands.describe(amount="바칠 센베이의 개수를 적어줘!")
async def snack(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("지휘관, 지금 나를 놀리는 거야? 장난치면 천벌을 내릴 거야! 🐉")
    elif amount < 5:
        await interaction.response.send_message(f"음, {amount}개라니... 조금 부족하지만 정성을 봐서 맛있게 먹어주지! 바삭바삭... 후후후.")
    else:
        await interaction.response.send_message(f"오오! {amount}개나! *꼬리를 기분 좋게 살랑거린다* 지휘관, 역시 최고야! 오늘 마사지는 내가 특별히 해주지! ♪")

@bot.tree.command(name="알람", description="용신님이 지휘관의 일정을 챙겨줄게!")
@app_commands.describe(분="몇 분 뒤에 알려줄까?", 내용="무슨 일인지 적어줘!")
async def alarm(interaction: discord.Interaction, 분: int, 내용: str):
    if 분 <= 0:
        await interaction.response.send_message("장난쳐? 제대로 된 시간을 말하라고! 천벌을 내릴 거야! 🐉")
        return
    
    # 먼저 알겠다고 대답하기
    await interaction.response.send_message(f"오호, 알았어. {분}분 뒤에 '{내용}'(이)라고 알려주면 되는 거지? 이 위대한 용신님만 믿고 마음 푹 놓고 있어! 후후후.")
    
    # 지정된 분(minutes)만큼 비동기로 대기
    await asyncio.sleep(분 * 60)
    
    # 시간이 되면 멘션과 함께 알림!
    await interaction.followup.send(f"<@{interaction.user.id}> 지휘관! 시간 다 됐어! '{내용}' 할 시간이야! 자, 용신님이 귀찮음을 무릅쓰고 알려줬으니 공물(센베이)을 바치도록 해♪")

# ---------------------------------------------------------
# 6. 기존 제미나이 대화 기능 (client를 bot으로 이름만 바꿨어!)
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot:
        return

    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()

        if user_id not in chat_sessions:
            past_history = load_history_from_db(user_id)
            chat_sessions[user_id] = model.start_chat(history=past_history)

        save_to_db(user_id, "user", user_input)
        sent_message = await message.reply("으음... (용신님 생각 중... 🐉)")

        async with message.channel.typing():
            try:
                response = await chat_sessions[user_id].send_message_async(user_input, stream=True)
                
                full_text = ""
                chunk_count = 0

                async for chunk in response:
                    full_text += chunk.text
                    chunk_count += 1
                    
                    if chunk_count % 5 == 0:
                        await sent_message.edit(content=full_text + " 🐉...")
                        await asyncio.sleep(0.1)

                await sent_message.edit(content=full_text)
                save_to_db(user_id, "model", full_text)

            except Exception as e:
                print(f"용신님의 마력 회로에 이상 발생!: {e}")
                await sent_message.edit(content="으윽... 지휘관, 사악한 힘이 너무 강해서 잠시 머리가 어질어질해. 다시 말해줄래? 후후후...")

bot.run(DISCORD_TOKEN)