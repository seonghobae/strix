# agents.md 작성/유지 가이드 (repo-local)

이 문서는 **AGENTS.md 형식(https://agents.md/)** 을 이 저장소에서 어떻게 작성/유지할지 구체화한다.

## 1) 목적

- 에이전트가 작업에 필요한 **정확한 실행/검증 지침**을 빠르게 찾도록 한다.
- README와 분리된 **에이전트 전용 규약**을 제공한다.

## 2) 위치와 스코프

- 루트 기준 문서 위치: `AGENTS.md`
- 하위 디렉토리/서브패키지가 있으면 **가까운 AGENTS.md가 우선**한다(agents.md 공식 FAQ).

## 3) 기본 템플릿

```
# AGENTS.md
## Setup commands
## Build/Test commands
## Code style
## Testing instructions
## Security considerations
## PR/Commit instructions
```

## 4) 반드시 포함할 내용

- 프로젝트/범위 요약
- 설치/실행/테스트 명령
- 코드 스타일/규칙
- 보안 주의사항(시크릿/접근 제약)
- PR/커밋 규칙(필요 시)

## 5) 성능 저하를 막는 방법 (조사 기반 요약)

agents.md 문서에 **테스트 명령을 적으면 에이전트가 실행**한다는 공식 FAQ가 있다.
따라서 다음을 기본값으로 한다:

- **명령 최소화**: 꼭 필요한 테스트/체크만 기재
- **스코프 한정**: 모노레포는 디렉토리별 AGENTS.md로 분리
- **비용 큰 작업은 명시적 조건 부여**: 예) “통합 테스트는 변경이 X에 영향 줄 때만”

## 6) 업데이트 원칙 (상시 갱신)

- 에이전트 동작/규칙 변경 시 **AGENTS.md와 이 문서를 동기화**
- 구조/동작 변경이 있으면 `ARCHITECTURE.md` 날짜 갱신

## 7) 유지보수 워크플로우

1. 변경 필요 발생(규칙/명령 변경)
2. `AGENTS.md` 갱신
3. 관련 정책 문서 확인(`docs/engineering/acceptance-criteria.md`)
4. PR continuity로 기존 PR 연결

## 8) 참고 (근거)

- https://agents.md/ (FAQ 포함)
