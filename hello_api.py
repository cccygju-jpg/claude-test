"""
Claude API 연결 테스트용 스크립트.
.env 파일의 ANTHROPIC_API_KEY를 읽어 Claude에게 간단한 요청을 보내고
응답이 정상적으로 오는지 확인한다.
"""
import os
import sys

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key or api_key.strip() == "" or "여기에" in api_key:
    sys.exit("[오류] .env 파일에 ANTHROPIC_API_KEY가 설정되어 있지 않습니다.")

client = Anthropic(api_key=api_key)

company_info = (
    "한빛정밀은 자동차 부품을 생산하며, "
    "생산관리팀은 생산 계획과 라인 운영을 맡는다."
)

response = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=200,
    messages=[
        {
            "role": "user",
            "content": (
                f"다음 회사 정보를 참고해서 회사와 팀을 한 문장으로 소개해줘.\n\n"
                f"{company_info}"
            ),
        }
    ],
)

print(response.content[0].text)
