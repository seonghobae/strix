# Skills / Subagents / MCP 역할 정리

이 문서는 **Skills, Subagents, MCP Tools의 역할과 충돌 해소 규칙**을 정의한다.

## 역할

- **Primary agent**: 전체 오케스트레이션(계획/위임/통합/요약) 책임
- **Skills**: 작업 방법(프로세스)을 규정하는 워크플로우
- **Subagents**: 좁은 범위의 구현/검증 담당(품질·증적 수집 포함)
- **MCP Tools**: 외부 시스템 실행 인터페이스(정책이 아닌 기능)

## 우선순위/충돌 해소

1. **Authoritative policy**: `prompts/build.txt`, `prompts/plan.txt`, `docs/engineering/acceptance-criteria.md`
2. **Skill workflow**: 해당 스킬이 적용되면 워크플로우를 우선한다.
3. **Subagent guidance**: 스킬/정책과 충돌하지 않는 범위에서만 적용.
4. **MCP Tools**: 도구 제약은 정책을 대체하지 않는다. 불가 시 `BLOCKED`로 근거 기록.
   - 근거가 없을 때는 MCP search/webfetch를 우선 사용하고, 실패 시 `BLOCKED`.

## 비대화형 원칙

- 질문/선택 요청 금지
- 안전한 기본값으로 진행하고 `ASSUMPTION` 기록
- 불가 시 `BLOCKED` (명령/근거 포함)

## Sequential-thinking MCP

- **항상 사용**이 기본값이다.
- 도구가 불가하면 텍스트 단계화로 대체하고 근거를 남긴다.

## Memory MCP

- **항상 사용**이 기본값이다.
- 반복/지속되는 사용자 선호, 정책, 결정, 환경 정보를 memory에 기록하고 재사용한다.
- Skill 워크플로우보다 **memory 기록/재사용이 우선**이며, 스킬 단계 내에 기록을 포함한다.

## 참고

- `docs/agents/README.md`
- `docs/engineering/acceptance-criteria.md`
