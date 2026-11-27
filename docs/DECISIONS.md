# 결정 기록

결정 하나를 「맥락 → 결정 → 결과」로 짧게 적는다. 새 것이 아래. 뒤집을 때는 지우지 않고 「대체됨(→ D번호)」을 단다.

## D1. 표준 하네스와 공용 CI (2026-11-24)

- **맥락:** 세션 규칙·작업 상황·CI가 저장소마다 달랐다. CI 단계가 다른 저장소들과 거의 같은데 따로 적혀 있었다.
- **결정:** CLAUDE.md에 세션 규칙, 작업 상황은 로컬 `state.md` 하나(`CLAUDE.local.md`가 가져옴, git 밖). CI는 공용 재사용 워크플로 `fairyofdata/Concordia`의 `python-tests.yml@v1`과 `hygiene.yml@v1`을 부른다. `.gitignore`에 `_private/`·`*.private.*`.
- **결과:** CI 단계를 고칠 일은 Concordia 한 곳에서. 대가: Concordia `v1`이 옮겨지면 이 저장소 CI도 따라 바뀐다.

## D2. 표기 이름을 저장소 이름 Neutralize4KRJP 하나로 (2026-11-27)

- **맥락:** 저장소 이름을 `LLM_NAKOJA`에서 Neutralize4KRJP로 바꾼 뒤에도 README 제목 괄호·안내 문장·그림 설명, `CLAUDE.md`, 앱 화면 제목·배지, docstring에 옛 앱 이름 LLM-NAKOJA가 현재 이름처럼 남아 있었다. 2026-11-27 작성자가 공개 저장소 이름 기준으로 맞추라고 했다.
- **결정:** 위 자리를 Neutralize4KRJP로 쓴다. README에는 옛 이름 안내 한 줄만 둔다(저장소 옛 이름 `LLM_NAKOJA`, 앱 이름 LLM-NAKOJA).
- **결과:** 패키지·파일 이름(`src/nakoja`, `NAKOJA_Preview.png`)과 `pyproject.toml`의 배포 이름 `llm-nakoja`는 그대로다. 바꾸면 import 경로와 설치 이름이 바뀐다.
