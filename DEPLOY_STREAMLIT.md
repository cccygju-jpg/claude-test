# Streamlit Community Cloud 배포 안내 (공통 문제 해결 제안서)

## 배포에 쓰는 파일
- `app.py` : 웹 화면 (진입 파일)
- `problem_proposal.py` : 제안서 생성 로직(CLI와 공용)
- `requirements.txt` : 의존 패키지
- `.streamlit/secrets.toml.example` : Secrets 형식 예시(실제 값 없음)

## 배포 순서
1. 위 파일들을 GitHub 저장소에 올립니다. (`.env`, `.streamlit/secrets.toml`은 `.gitignore`로 제외됨)
2. https://share.streamlit.io 에서 GitHub로 로그인 → **Create app** → 저장소·브랜치(`main`)·
   Main file path `app.py` 선택.
3. **Advanced settings > Secrets**에 아래를 붙여넣고 값을 채웁니다.
   ```toml
   ANTHROPIC_API_KEY = "실제-API-키"
   APP_PASSWORD = "접속-비밀번호"
   ```
4. Deploy. 배포 후에는 앱 설정 > Sharing에서 접근 가능한 사람을 제한하는 것을 권장합니다.

## 보안·비용 주의
- API 키는 Secrets에만 둡니다. 코드·저장소·채팅에 붙여넣지 마세요.
- `APP_PASSWORD`가 없으면 앱이 열리지 않도록 되어 있습니다(URL을 아는 사람이 API 비용을
  쓰는 것을 막기 위함). 비밀번호는 충분히 길게 정하세요.
- 연속 실행은 30초 간격으로 제한되고, 파일은 최대 10개·개당 200KB입니다(`app.py` 상단에서 변경).
- 올린 보고서 내용은 Claude API로 전송됩니다. 개인정보·기밀 자료는 올리지 마세요.
- Community Cloud의 서버 파일은 유지되지 않으므로 결과는 화면의 "내려받기"로 저장합니다.

## 로컬에서 먼저 확인하려면
```
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   (값 채우기)
streamlit run app.py
```
