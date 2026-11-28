# 0002. 표기 이름을 저장소 이름 Neutralize4KRJP 하나로

- 상태: 채택 (2026-11-27)

- **맥락:** 저장소 이름을 `LLM_NAKOJA`에서 Neutralize4KRJP로 바꾼 뒤에도 README 제목 괄호·안내 문장·그림 설명, `CLAUDE.md`, 앱 화면 제목·배지, docstring에 옛 앱 이름 LLM-NAKOJA가 현재 이름처럼 남아 있었다. 2026-11-27 작성자가 공개 저장소 이름 기준으로 맞추라고 했다.
- **결정:** 위 자리를 Neutralize4KRJP로 쓴다. README에는 옛 이름 안내 한 줄만 둔다(저장소 옛 이름 `LLM_NAKOJA`, 앱 이름 LLM-NAKOJA).
- **결과:** 패키지·파일 이름(`src/nakoja`, `NAKOJA_Preview.png`)과 `pyproject.toml`의 배포 이름 `llm-nakoja`는 그대로다. 바꾸면 import 경로와 설치 이름이 바뀐다.
