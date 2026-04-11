# 중국어 호환 레이어 정책

## 왜 필요한가
- 기존 저장 로그, 리포트, 대시보드 데이터에는 아직 중국어 source 문자열이 남아 있을 수 있다.
- `frontend/src/i18n/index.js`와 `dashboard/lib/dashboard-text.js`는 새 데이터와 옛 데이터를 함께 받기 위한 호환 레이어다.

## 운영 기준
- 중국어 source key는 즉시 삭제하지 않는다.
- 새 backend 문자열에는 한국어 alias를 추가한다.
- 정규화 동작은 유지하고, 새 source만 alias에 더한다.

## 제거 전 확인
- `cd frontend && npm run build`
- `cd dashboard && npm run build`
- 대시보드에 별도 렌더 확인이 가능하면, 해당 화면에서 리포트와 로그를 직접 열어 확인한다.
- 제거할 key가 tracked saved/dashboard data에 남아 있는지 `git grep -n "<source key>" -- .` 또는 해당 fixture/sample 경로 검색으로 확인한다.
- 그 key를 쓰던 저장 리포트/로그 fixture 또는 sample 하나를 골라, 제거 후에도 그 key가 필요 없는지 수동 렌더링으로 확인한다.

## 제거 가능 조건
- 신규 로그 source가 전부 한국어다.
- 저장된 리포트가 더 이상 해당 key를 참조하지 않는다.
- 관련 regression 확인과 수동 렌더링 확인이 모두 통과한다.
