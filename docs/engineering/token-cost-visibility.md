# Token Cost Visibility (Spent Token Cost)

이 문서는 **spent token cost가 기본 출력에 나타나지 않을 때의 처리 기준**을 정의한다.

## 기본 원칙

- 런타임이 비용/토큰 사용량을 직접 표시하지 않으면, **세션 로그 기반의 오프라인 분석**을 기본값으로 한다.
- 로그가 없으면 `BLOCKED`로 기록한다.

## 오프라인 분석 (기본값)

이 저장소에는 세션 JSONL 기반 토큰/비용 분석 스크립트가 포함되어 있다:

```
python3 superpowers/tests/claude-code/analyze-token-usage.py <session-file.jsonl>
```

출력에는 입력/출력/캐시 토큰과 **추정 비용**이 포함된다.

## BLOCKED 기준

- 세션 로그 파일이 없거나 접근 불가일 때
- 런타임이 usage 필드를 기록하지 않을 때

이 경우 `BLOCKED`에 **누락된 입력/파일 경로**를 명시한다.

## 참고

- `superpowers/tests/claude-code/analyze-token-usage.py`
