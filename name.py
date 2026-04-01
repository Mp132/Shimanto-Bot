from google import genai

client = genai.Client(api_key="AIzaSyB6JP4gBV5Y2S9dlavOzuHEyqV168MA0lE")

for model in client.models.list():
    # 모든 모델의 이름과 지원 기능을 출력해서 확인해보기
    print(f"모델명: {model.name} / 지원기능: {model.supported_actions}")