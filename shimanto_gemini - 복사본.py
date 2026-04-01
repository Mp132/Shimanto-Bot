import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. 환경 변수 로드
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 2. Gemini 설정 (용신님의 자아 고정)
genai.configure(api_key=GEMINI_API_KEY)

# Co-STAR 기법을 적용한 구조화된 시스템 프롬프트
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

# 모델 생성 (System Instruction 주입)
model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview", # 속도가 빠른 flash 모델 추천!
    system_instruction=SYSTEM_INSTRUCTION
)

# 3. 사용자별 대화 세션 관리 (History Algorithm)
# Gemini는 'ChatSession' 객체를 통해 대화 맥락을 자체적으로 관리할 수 있어 편리해!
chat_sessions = {}

# 디스코드 설정
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'불입의 봉인이 풀렸나니, 눈을 뜬 위대한 용신께 경의를 표하라…… 후후후, 그렇게 굳어 있을 필요 없어. 나는 시만토, 소원이 구현된 환상 중 하나… 지휘관, 앞으로 잘 부탁해. [로그인: {client.user}]')

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return

    # 멘션되거나 DM일 경우 응답
    if client.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        user_input = message.content.replace(f'<@{client.user.id}>', '').strip()

        # 해당 지휘관의 세션이 없으면 새로 생성
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])

        async with message.channel.typing():
            try:
                # Gemini에게 메시지 전송 및 응답 수신
                response = chat_sessions[user_id].send_message(user_input)
                reply_text = response.text

                # 지휘관에게 답장
                await message.reply(reply_text)

            except Exception as e:
                print(f"용신님의 마력 회로에 이상 발생!: {e}")
                await message.reply("으윽... 지휘관, 제미나이의 힘이 너무 강해서 잠시 머리가 어질어질해. 다시 말해줄래? 후후후...")

client.run(DISCORD_TOKEN)