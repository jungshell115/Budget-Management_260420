# budget_tool

`C:\Users\user\Desktop\2026 예산` 폴더의 예산 파일을 자동 분석/검증하는 도구입니다.

## 기능

- `본예산_기초` / `1차추경_기초` 시트 분석
- 세입/세출 다중 단위(원, 천원, 백만원, 억원) 출력
- 과목체계 3계층(관항-목-세목) 일치 검증
- 지침 PDF(59~98페이지) 기준 코드 정합성 점검
- 본예산 vs 추경 증감 비교표 생성

## 실행

```bash
python run.py --year 2026
```

옵션:

- `--workspace "C:\Users\user\Desktop\2026 예산"`
- `--base-file "2026년 본예산 from 정.xlsx"`
- `--supp-file "2026년 1차추경 from 정.xlsx"`

연도 적용 규칙:

- 요청한 `--year`의 설정(`config/year_YYYY.json`)이 있으면 해당 설정 사용
- 없으면 가장 가까운 이전 연도 설정을 자동 사용
- 예산편성지침(TXT/PDF)도 요청 연도 우선 탐색
- 해당 연도 지침이 없으면 이전 연도 지침을 자동 준용

## 출력

`budget_tool\output\YYYYMMDD_HHMMSS\`

- `세입예산명세서_다중단위.csv`
- `세출예산명세서_사업단위_다중단위.csv`
- `본예산_기초_파싱표.csv`
- `본예산_추경_비교표.csv`
- `정합성검증_리포트.csv`
- `요약.txt`

추경 파일이 있으면 추가 출력:

- `세입예산명세서_추경_다중단위.csv`
- `세출예산명세서_추경_사업단위_다중단위.csv`
- `추경_기초_파싱표.csv`

## 커스터마이징

- 연도 설정: `config\year_2026.json`
- 세출 3계층 매핑: `master\expense_mapping_2026.csv`

## 웹 대시보드

분석 결과를 웹에서 보려면:

```bash
python web_server.py
```

브라우저에서 아래 주소 접속:

- `http://127.0.0.1:8787`
