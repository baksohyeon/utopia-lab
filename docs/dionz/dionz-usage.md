# Dionz 팀에서 Utopia 쓰는 법

`utopia-lab`(이 포크)의 `lab` 브랜치로 띄운 Utopia 위에 Dionz 문서 셋을 얹어 쓰는 방법이다.
upstream 문서가 아니라 **우리 배포에만 해당하는 운영 메모**라 `docs/dionz/`에 둔다.

## 무엇이 어디에 있나

| 것 | 위치 |
|---|---|
| 앱 | `http://192.168.2.212:1516` (사내망), `http://100.87.231.1:1516` (Tailscale). Funnel은 데모 때만 켠다 |
| 지식베이스 | `dionz` 하나. 첫 계정이 관리자 |
| 소스 3개 | `ai-lab`(일지·사후분석·결정), `dionz-notion`(ideation-v1의 노션 미러와 _Knowledge), `dionz-ops`(charter·decisions·journal·runbooks) |
| 채팅 모델 | MLX `Qwen3-30B-A3B-Instruct-2507-4bit`, `http://host.docker.internal:8080/v1` |
| 임베딩 모델 | `Shitao/bge-m3`(1024차원), `http://host.docker.internal:8766/v1` |
| 원본 | ai-lab, ideation-v1, dionz-ops 레포. **Utopia는 읽기 전용 조회·추론 층**이고 정본은 계속 그 레포들이다 |

## 문서 넣기: `scripts/push-ai-lab.py`

세 레포의 마크다운을 읽어 Utopia API 소스로 밀어넣는 스크립트다. 표준 라이브러리만 쓰고, 원본 레포에는 아무것도 쓰지 않는다.

```bash
# 어떤 파일이 어떤 날짜로 들어갈지 미리 보기 (네트워크 없음)
python3 scripts/push-ai-lab.py --corpus ai-lab --dry-run

# 실제 푸시. 토큰은 Library → 해당 소스 → Token 다이얼로그에서 그때 읽는다. 파일에 적지 않는다
UTOPIA_SOURCE_ID=<소스 UUID> UTOPIA_INGEST_TOKEN=utp_... python3 scripts/push-ai-lab.py --corpus ai-lab
```

| corpus | 소스 UUID | 들어가는 것 | 빼는 것 |
|---|---|---|---|
| `ai-lab` | `01a06b4b-4100-7a80-9c36-5365a4244cab` | `docs/journal/2026/**`, `docs/journal/postmortem/`, `docs/decisions/` | `*.raw.md`, README, views, registry(엔티티 사전이라 문서가 아님) |
| `ideation-v1` | `01a06b5a-af4d-71d1-a07c-8f0ccce812d6` | `dionz/_Source-Notion/**`, `dionz/_Knowledge/**` | `_loop/`(프롬프트), 허브·대시보드, `_sync-log`, `_deleted`, `_unfiled`, `_Active/`(ai-lab 미러) |
| `dionz-ops` | `01a06b92-cd47-7f63-a334-706379ae8cb9` | `docs/**` | `transcripts/`(세션 녹취), patch 폴더 |

문서의 시각(`doc_time`)은 frontmatter의 `decided_at` → `created_at` → `updated_at` 순으로 읽고, 없으면 파일명·폴더명의 날짜, 그것도 없으면 본문 첫 줄의 "업데이트: 2026년 6월 29일" 같은 한국어 날짜를 읽는다. 전부 없으면 서버가 수집 시각을 쓴다.

**같은 파일을 다시 밀어도 안전하다.** 경로가 문서의 신원이라 내용이 같으면 `unchanged`, 바뀌었으면 `updated`로 새 버전이 쌓이고 이전 추출은 출처와 함께 남는다. 그래서 정기 동기화는 그냥 세 줄을 다시 돌리는 것이다.

## 일상 루프

### 1. 기록은 원본 레포에 그대로 한다

일지, 사후분석(`/postmortem`), 결정 스펙, blame, 회고는 지금처럼 각 레포에 쓴다. Utopia를 의식해서 형식을 바꿀 필요는 없다. 다만 두 가지가 있으면 그래프가 훨씬 좋아진다.

- **frontmatter에 날짜.** `created_at`(일지·사후분석), `decided_at`(결정). 이게 사실의 유효 시작일이 된다.
- **문장에 날짜와 주어.** "9/3 재배정으로 a6000-0은 장기기억 서빙 몫이 됐다"처럼 언제, 무엇이, 어떻게 바뀌었는지가 한 문장에 있으면 추출기가 `valid_from`이 있는 사실로 뽑는다. "재배정함" 한 줄은 못 뽑는다.

### 2. 커밋 뒤 푸시 스크립트를 돌린다

`/postmortem`으로 `docs/journal/postmortem/009-....md`가 생기면 ai-lab 레포에 커밋한 뒤 `--corpus ai-lab`을 한 번 돌린다. 새 파일만 `created`로 들어가고 나머지는 `unchanged`다. 몇 초 안에 `Ready`(검색 가능)가 되고, 그래프 추출은 뒤에서 청크당 LLM 1회씩 돈다.

수동이 귀찮아지면 각 레포의 post-commit 훅이나 launchd에서 같은 명령을 돌리면 된다. 토큰은 환경변수나 키체인으로만 넘긴다.

### 3. 읽는 쪽

| 탭 | 언제 |
|---|---|
| **Search** | "그거 어디 적었지". 전문검색 + bge-m3 벡터 하이브리드. 결과를 누르면 문서 뷰어의 그 구절로 간다 |
| **Chat** | "X가 9월 초에 뭘 담당했어", "지난주에 뭐가 바뀌었어". 문서와 그래프를 같이 걸어 다니며 인용 붙여 답한다 |
| **Graph** | 엔티티 클릭 → 사실 타임라인과 근거 문장. 하단 슬라이더로 시점을 돌리면 그때 참으로 믿었던 그래프가 나온다 |
| **Review** | 같은 것 다른 이름(Duplicates), 서로 어긋나는 사실(Conflicts), 낮은 신뢰도(Low confidence). 승인·거절은 원장에 남는다 |
| **Ontology** | 코퍼스에서 자주 나온 미등록 타입·관계가 제안으로 쌓인다. 채택하면 다음 추출부터 그 어휘를 쓴다 |

### 4. `/postmortem`과 Utopia를 같이 쓰는 가장 좋은 방법

사후분석의 가치는 "같은 증상을 다음에 먼저 찾는 것"인데, README의 표는 손으로 유지하는 인덱스다. Utopia에 들어가면 그 표가 자동으로 검색되고 시간축에 놓인다. 권하는 순서는 이렇다.

1. **쓰기 전에 먼저 묻는다.** 뭔가 깨졋을 때 Chat에 증상을 그대로 적는다. "MLX 임베딩 서버가 안 뜬다", "funnel status는 on인데 밖에서 안 붙는다". 기존 사후분석 001, 003이 인용과 함께 나오면 새로 쓸 일이 없다.
2. **쓸 때는 규약대로.** `NNN-YYYYMMDD-작성자-slug.md`, frontmatter에 `type: Postmortem`, `created_at`, `status`. 본문에는 오판한 가설과 기각 근거를 남긴다. 이게 추출기가 뽑는 "X라고 믿었다가 Y로 정정했다"는 인식 변경 사실이 된다.
3. **커밋하고 푸시 스크립트.** 위 2번.
4. **며칠 뒤 Review 탭.** 사후분석에서 나온 사실이 결정 스펙과 어긋나면 Conflicts에 뜬다. 예: serving-decision의 "사내 GPU는 성준님 몫"과 9/3 재배정 사실. 이게 잡히는지가 이 도구가 제값을 하는지의 시험이다.
5. **승격은 사람이.** 사후분석에서 나온 규칙(예: "1차 자료가 0건이면 원인 절을 쓰지 않는다")을 runbook으로 올리는 판단은 계속 사람이 한다. Utopia는 "이 규칙이 어느 사건에서 나왔나"를 거슬러 보여주는 역할이다.

### 5. Claude Code에서 직접

개인 토큰(사용자 메뉴 → Tokens, scope `write`)을 만들고 KB 단위 MCP를 붙인다.

```bash
claude mcp add --transport http utopia-dionz \
  http://localhost:1516/api/v1/kbs/01a06b2b-5d2b-7210-9ed4-b45b528a9673/mcp \
  --header "Authorization: Bearer utp_pat_..."
```

세션에 `search_chunks`, `search_docs`, `get_document`, `entity_facts`(특정 시점의 사실, 기간 내 변경), `query_data`, `remember`가 붙는다. `remember`로 남긴 문장은 **Review → Awaiting your nod**에 쌓이고 사람이 승인해야 사실이 된다. 에이전트가 멋대로 그래프를 오염시키지 못하는 관문이다.

## 운영 메모

- **MLX 서버는 `--max-tokens 4096`으로 띄운다.** 기본 512에서는 추출 JSON이 잘려 엔티티 뒤에 오는 사실이 통째로 사라진다(`truncated_reply` 드롭).
- **chat 모델 동시 요청은 1.** `mlx_lm.server`는 요청을 배치하지 못해서 2 이상이면 GPU를 나눠 쓰며 전부 느려지고 300초 타임아웃에 걸린다. Administration → Deployment에서 chat 행을 1로, embed 행은 4, Background workers는 32. Default만 올리면 chat도 따라가니 **chat 행에 개별 값을 꼭 넣는다.**
- **워커 수를 낮게 두면 파싱이 굶는다.** 추출 잡이 모델 순번을 기다리는 동안에도 워커 자리를 잡고 있어서, 워커 8에 추출 8개면 새 문서 파싱이 시작조차 못 한다. 32 이상으로 둔다. (upstream에도 있는 스케줄링 결함, 고칠 후보)
- **`Failed`는 포기가 아니다.** 큐가 3회까지 백오프로 재시도한다. `Retry failed`는 3/3까지 갔을 때만 누른다. 진행 중에 누르면 같은 문서에 잡이 두 개 생긴다.
- **`N dropped`는 대부분 필터다.** `not_an_entity_name`(문장을 엔티티로 내놓은 것), `object_missing`은 버리는 게 맞다. `truncated_reply`만 나쁜 신호다.
- **맥이 잠들면 전부 멈춘다.** 긴 추출은 전원 연결하고 잠자기를 끈다.
- **백업 = `data/` 디렉터리 + Postgres 볼륨.** 봉인 키(`data/secret.key`)가 없으면 저장된 자격증명을 못 읽는다.
- **upstream은 v0.1, 마이그레이션은 전진만.** 업그레이드 전에 백업.
