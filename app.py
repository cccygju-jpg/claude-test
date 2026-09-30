"""
부서 보고서 공통 문제 해결 제안서 - Streamlit 웹 화면.

실행(로컬): streamlit run app.py
배포: Streamlit Community Cloud (DEPLOY_STREAMLIT.md 참고)

제안서 생성 로직은 problem_proposal.py를 그대로 사용한다.
API 키와 접속 비밀번호는 코드나 저장소가 아니라 Streamlit Secrets에서만 읽는다.
"""
import hmac
import os
import time
from datetime import datetime

import streamlit as st

import problem_proposal as pp

MAX_FILES = 10
MAX_FILE_BYTES = 200 * 1024  # 파일당 200KB
COOLDOWN_SECONDS = 30  # 연속 호출 방지(API 비용 보호)

st.set_page_config(page_title="공통 문제 해결 제안서", page_icon="📄", layout="wide")


def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:  # secrets 파일이 없는 로컬 실행 등
        value = ""
    return (value or os.environ.get(name, "")).strip()


def check_password() -> bool:
    """APP_PASSWORD가 설정되어 있어야만 화면을 연다(미설정이면 막음: API 비용 보호)."""
    expected = get_secret("APP_PASSWORD")
    if not expected:
        st.error(
            "APP_PASSWORD가 설정되어 있지 않아 앱을 열 수 없습니다. "
            "Streamlit Secrets에 APP_PASSWORD를 추가해 주세요."
        )
        return False
    if st.session_state.get("authed"):
        return True
    entered = st.text_input("접속 비밀번호", type="password")
    if entered:
        if hmac.compare_digest(entered.encode(), expected.encode()):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 맞지 않습니다.")
    return False


def read_uploads(files):
    if len(files) > MAX_FILES:
        raise pp.ProposalError(f"[오류] 파일은 최대 {MAX_FILES}개까지 올릴 수 있습니다.")
    reports = []
    for f in files:
        data = f.getvalue()
        if len(data) > MAX_FILE_BYTES:
            raise pp.ProposalError(
                f"[오류] {f.name}: 파일 크기가 {MAX_FILE_BYTES // 1024}KB를 넘습니다."
            )
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise pp.ProposalError(f"[오류] {f.name}: UTF-8 텍스트 파일이 아닙니다.")
        if not text.strip():
            raise pp.ProposalError(f"[오류] {f.name}: 파일 내용이 비어 있습니다.")
        reports.append(pp.parse_report(f.name, text))
    if len(reports) < 2:
        raise pp.ProposalError("[오류] 공통 문제를 찾으려면 보고서가 2개 이상 필요합니다.")
    return reports


def main():
    st.title("부서 보고서 공통 문제 해결 제안서")
    st.caption(
        "여러 부서 보고서에서 공통 문제를 찾아 해결 방안을 제안하는 초안을 만듭니다. "
        "[제안]은 원문에 없는 새 제안이며, 근거가 부족한 내용은 '확인 필요'로 표시됩니다."
    )

    if not check_password():
        return

    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY가 Streamlit Secrets에 설정되어 있지 않습니다.")
        return

    st.warning(
        "올린 보고서 내용은 분석을 위해 Claude API(외부 서비스)로 전송됩니다. "
        "개인정보·기밀·실제 고객 정보가 있는 자료는 올리지 마세요."
    )

    files = st.file_uploader(
        "부서별 보고서 파일 (.md, .txt / 2개 이상)",
        type=["md", "txt"],
        accept_multiple_files=True,
    )

    if st.button("제안서 만들기", type="primary", disabled=not files):
        last = st.session_state.get("last_run", 0.0)
        wait = COOLDOWN_SECONDS - (time.time() - last)
        if wait > 0:
            st.info(f"연속 요청을 막기 위해 {int(wait) + 1}초 뒤에 다시 시도해 주세요.")
        else:
            st.session_state["last_run"] = time.time()
            try:
                reports = read_uploads(files)
                with st.spinner("Claude가 제안서를 작성 중입니다. 1분 안팎 걸릴 수 있습니다..."):
                    result = pp.call_claude(api_key, pp.build_user_prompt(reports))
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.session_state["result"] = {
                    "document": pp.build_document(result, reports, timestamp),
                    "problems": pp.check_structure(result),
                    "filename": f"공통문제_해결제안서_{timestamp}.md",
                }
            except pp.ProposalError as e:
                st.session_state.pop("result", None)
                st.error(str(e))
            finally:
                st.session_state["last_run"] = time.time()  # 종료 시점부터 쿨다운

    result = st.session_state.get("result")
    if result:
        if result["problems"]:
            st.warning("결과 형식에 문제가 있습니다. 사람이 확인해 주세요: " + " / ".join(result["problems"]))
        st.download_button(
            "제안서 내려받기 (.md)",
            data=result["document"].encode("utf-8"),
            file_name=result["filename"],
            mime="text/markdown",
        )
        st.divider()
        st.markdown(result["document"])


main()
