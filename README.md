# MARKET PULSE — 무료 Gemini 2단계 AI 버전

기존 MARKET PULSE 대시보드를 유지하면서 **Gemini 3.6 Flash → Gemini 2.5 Pro**로 분석을 2번 수행합니다. Pro 요청이 무료 한도 초과 등으로 실패하면 **Flash 분석만 게시**하며, 홈페이지에 'Pro 재검토 실패'가 명시됩니다. 두 모델 모두 같은 공개 RSS 제목·요약과 시장 자료를 사용하기 때문에 **둘의 합의가 진위 검증 또는 예측 적중률 향상을 보장하지 않습니다.**

## 자동 작동 과정
1. Google 뉴스 RSS(주식·부동산·채권), FRED 시장 통계, Yahoo Finance 한국 주가지수(비공식)를 수집합니다.
2. `gemini-3.6-flash` 모델이 1차 시장 방향성 브리핑을 작성합니다. 모델이 계정에서 사용 불가능하면 `gemini-2.5-flash`로 대체를 시도합니다.
3. `gemini-2.5-pro` 모델이 기사 근거·정합성·금리와 채권가격 관계·과도한 확신을 검토하고 새 보고서를 작성합니다.
4. 모델별 결과·검토 상태를 `site/data/latest.json`에 저장하고 GitHub Pages에 발행합니다.
5. GitHub Actions 스케줄은 매일 00:07 UTC(한국시간 09:07)이며 실제 시각은 지연될 수 있습니다.

## 처음 설치 (직접 따라하기)
1. [Google AI Studio](https://aistudio.google.com/api-keys)에서 *무료 API 등급*으로 키를 발급받습니다. Google AI Plus 구독과 API 과금은 별도입니다.
2. [GitHub 새 저장소](https://github.com/new)에서 `market-pulse`, `Public`, 기본 브랜치 `main`으로 만듭니다.
3. ZIP 압축을 풀고 **`market-pulse-dual-ai` 폴더 안의 파일과 폴더를 저장소 루트에 업로드**합니다. `.github/workflows/daily.yml`을 꼭 포함하세요.
4. `Settings → Secrets and variables → Actions → New repository secret`에서 **Name: `GEMINI_API_KEY`**, Secret: 실제 API 키를 입력합니다. 키를 코드나 웹페이지에 적지 마세요.
5. `Settings → Pages → Build and deployment → Source`를 `GitHub Actions`로 선택합니다.
6. `Actions → Daily Dual-AI Finance Briefing → Run workflow → main → Run workflow`로 첫 실행을 시작합니다.
7. `build`, `deploy`가 초록색으로 완료되면 `Settings → Pages → Visit site`를 확인합니다. 주소 예시: `https://내계정.github.io/market-pulse/`.
8. 저장소의 `site/data/latest.json`에서 `ai.review_status`를 확인하세요.

## 이전 Gemini 홈페이지에서 업그레이드
기존 저장소에 다음 파일을 **덮어쓰기**하세요.

- `.github/workflows/daily.yml`
- `scripts/update_report.py`
- `site/index.html`
- `tests/test_update_report.py`
- `requirements.txt`

기존 `GEMINI_API_KEY`는 **그대로 재사용**합니다. `site/data/latest.json`은 첫 자동 실행으로 갱신되므로 기존 데이터가 중요하다면 백업하세요. **기존 `.github/workflows/daily.yml` 파일을 교체하는 것이 중요합니다.** 동일 저장소에 예전 자동 갱신 워크플로를 함께 남겨 두면 여러 번 실행됩니다.

## 모델 설정 (저장소에서 간편히 교체)
`.github/workflows/daily.yml` 파일 `Fetch news and build report` 단계의 환경변수를 편집합니다.

```yaml
env:
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  GEMINI_FLASH_MODEL: gemini-3.6-flash
  GEMINI_FLASH_FALLBACK: gemini-2.5-flash
  GEMINI_REVIEW_MODEL: gemini-2.5-pro
  ENABLE_PRO_REVIEW: "1"
```

- Pro 검토를 끄려면 `ENABLE_PRO_REVIEW: "0"`으로 수정합니다.
- 사용 모델명이 실제 프로젝트에 제공되는지 [Google AI Studio](https://aistudio.google.com/)에서 확인합니다.
- 처음에는 **무료 API 프로젝트의 사용량 한도**를 반드시 확인하세요. 유료 계정 연결 없이 운영하면 요청이 제한될 수 있습니다.

## 상태 확인

| `ai.status` | `ai.review_status` | 의미 |
|---|---|---|
| `ok` | `completed` | Flash 초안 + Pro 재검토 성공 |
| `ok` | `failed` | Flash 초안 게시, Pro 검토 실패 |
| `ok` | `not_run` | Flash 분석만 성공(검토 비활성화) |
| `error` | `not_run` | Flash도 실패하여 AI 분석 없음 |
| `not_configured` | `not_run` | API 키 누락 |

API 키와 모델별 사용 제한은 Actions 로그에서 확인할 수 있습니다. 공개 데이터에 키나 에러 세부내용은 기록하지 않도록 했습니다. 네트워크 문제·비공식 데이터 수집 제한으로 일부 자료가 비어 있을 수 있습니다. 부동산 실제 실거래가 시계열은 제공하지 않으므로 상승·하락은 정성 시나리오입니다.

## 비용·주의사항
- Google API **무료 요금제 사용 가능** 범위 내에서는 모델 호출료가 0원일 수 있습니다. 무료 한도는 모델·계정·프로젝트마다 다릅니다.
- API 무료 등급의 입력이 제품 개선에 사용될 수 있으므로 **공개 뉴스와 경제지표만 전송**합니다.
- Google AI Plus는 API 무료 한도를 자동으로 확대하지 않습니다.
- RSS/야후 비공식 데이터의 이용 조건, GitHub Pages의 사용 제한을 준수해야 합니다.
- 모델을 두 번 호출해도 실제 미래 가격을 정확히 예측한다는 보장은 없습니다.

공식 문서:
- [Gemini API 가격](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API 사용 제한](https://ai.google.dev/gemini-api/docs/rate-limits)
- [GitHub Actions 수동 실행](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
