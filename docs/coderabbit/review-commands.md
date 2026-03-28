# CodeRabbit PR Review Commands (GitHub)

> Source of truth: https://docs.coderabbit.ai/reference/review-commands.md
>
> This repo stores a **copyable, repo-local quick reference** so agents can act
> without relying on external browsing.
>
> Last verified: 2026-02-14

## NOTE (tooling)

이 저장소에는 `skills/coderabbit-review-commands/`도 함께 두었지만,
일부 실행 환경에서는 “Skill 목록”이 프로세스 시작 시점에 고정되어 **새로 추가한 스킬이 즉시 노출되지 않을 수 있다**.
그 경우에도 이 문서(`docs/coderabbit/review-commands.md`)를 **source-of-truth**로 사용한다.

## 핵심 원칙

- **모든 명령은 PR 코멘트/본문에서 `@coderabbitai` 멘션을 포함해야 동작**한다.
- **위치가 중요한 명령이 있다**(특히 `@coderabbitai ignore`는 PR *description*에만).

---

## Review control commands

### Manual review triggers

| Command | Where | What it does |
|---|---|---|
| `@coderabbitai review` | PR comment | 변경분(new changes) 중심의 incremental review 트리거 |
| `@coderabbitai full review` | PR comment | PR 전체를 처음부터 다시 리뷰 |

### Review flow control

| Command | Where | What it does | Gotchas |
|---|---|---|---|
| `@coderabbitai pause` | PR comment | 자동 리뷰 일시 중지 | 개발 중 리뷰 스팸 방지용 |
| `@coderabbitai resume` | PR comment | 자동 리뷰 재개 | pause 이후 사용 |
| `@coderabbitai ignore` | PR description (body) | 이 PR에서 자동 리뷰를 영구적으로 비활성화 | **코멘트에 쓰면 안 됨**. 다시 켜려면 PR description에서 해당 문구 제거 |

---

## Content generation commands

| Command | Where | What it does | Notes |
|---|---|---|---|
| `@coderabbitai summary` | PR description (placeholder) | PR summary가 들어갈 위치를 지정(placeholder) | “코멘드”라기보단 **자리표시자**. 설정으로 placeholder 문자열 변경 가능 |
| `@coderabbitai generate docstrings` | PR comment | docstring 생성 | CodeRabbit 설정에서 기능 enable 필요 |
| `@coderabbitai generate unit tests` | PR comment | unit test 생성 | CodeRabbit 설정에서 기능 enable 필요 |
| `@coderabbitai generate sequence diagram` | PR comment | 시퀀스 다이어그램 생성 | 복잡한 PR 설명에 유용 |

---

## Comment management

| Command | Where | What it does | Gotchas |
|---|---|---|---|
| `@coderabbitai resolve` | PR comment | CodeRabbit 코멘트를 **전부** resolve 처리 | 선택적 resolve 아님(실제로 해결했을 때만) |

---

## Information / diagnostics

| Command | Where | What it does |
|---|---|---|
| `@coderabbitai configuration` | PR comment | 현재 CodeRabbit 설정 표시 |
| `@coderabbitai help` | PR comment | 사용 가능한 커맨드 빠른 목록 |

---

## 운영 팁(안전 기본값)

- 큰 변경/리베이스/리팩토링 후에는 `@coderabbitai full review`를 우선 고려.
- 작업 중에는 `pause`로 리뷰 스팸을 줄이고, 마무리 시 `resume` 또는 `review`로 재개.
- `ignore`는 “이 PR은 CodeRabbit을 쓰지 않는다”는 의미이므로, 자동화를 기대하는 흐름에서는 사용하지 않는다.
