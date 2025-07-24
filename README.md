# TMH - Task Master Helper 🚀

**병렬 개발을 위한 Task Master 자동화 도구**

TMH는 [Task Master AI](https://github.com/eyal-taskmaster/task-master-ai)와 Git Worktree, Claude CLI를 연동하여 복수의 태스크를 병렬로 개발할 수 있게 해주는 Python 스크립트입니다.

## ✨ 주요 기능

- 🔍 **Ready 태스크 자동 감지**: 의존성이 해결된 작업 가능한 태스크들을 자동으로 찾습니다
- 🌳 **Git Worktree 자동 생성**: 각 태스크별로 독립적인 작업 환경을 만듭니다
- 🤖 **Claude CLI 통합**: AI 코딩 어시스턴트와 자동으로 연동됩니다
- 📋 **코드 리뷰 자동화**: Git diff를 기반으로 구조화된 리뷰 요청을 생성합니다
- 🔄 **Opus 검수 워크플로우**: 메인 프로젝트에서 AI 검수를 자동화합니다

## 🛠 필수 요구사항

설치가 필요한 도구들:

```bash
# Task Master AI CLI
npm install -g task-master-ai

# jq (JSON 처리)
brew install jq  # macOS
# 또는 apt-get install jq  # Ubuntu

# Claude CLI
# https://docs.claude.ai/claude-code 에서 설치

# Git (당연히 필요)
git --version
```

## 🚀 빠른 시작

### 1. TMH 설치

```bash
# 저장소 클론 또는 파일 다운로드
curl -O https://raw.githubusercontent.com/youyoung00/tmh/main/tmh.py
chmod +x tmh.py

# 또는 git clone
git clone https://github.com/youyoung00/tmh.git
cd tmh
```

### 2. 프로젝트 초기화

```bash
# Task Master 초기화
tm init

# PRD에서 태스크 생성 (선택사항)
tm parse-prd your-requirements.txt

# Claude CLI 토큰 설정 (한 번만)
claude setup-token
```

### 3. 병렬 개발 시작

```bash
# 1. Ready 태스크 확인
./tmh.py debug-ready

# 2. 병렬 작업 시작 (워크트리 생성 + VS Code 열기)
./tmh.py kickoff-ready-claude

# 3. 각 워크트리에서 수동 Claude CLI 실행
cd ../ws/task-name
./run_claude.sh

# 4. 작업 완료 후 코드 리뷰
./tmh.py generate-review 3,6,7
cat reviews/task_3_review.md | claude --dangerously-skip-permissions
```

## 📋 명령어 레퍼런스

### 태스크 관리
```bash
./tmh.py debug-ready           # Ready 태스크 확인
./tmh.py next                  # 다음 작업할 태스크 보기
./tmh.py show <id>             # 특정 태스크 상세 보기
./tmh.py set <status> <ids>    # 태스크 상태 변경
```

### 워크트리 & 병렬 작업
```bash
./tmh.py worktree-ready        # Ready 태스크들의 워크트리 생성
./tmh.py kickoff-ready         # 프롬프트 + 워크트리 생성
./tmh.py kickoff-ready-claude  # 풀 자동화 (VS Code + Claude CLI)
```

### 프롬프트 생성
```bash
./tmh.py prompt <id>           # 특정 태스크 프롬프트 생성
./tmh.py prompt-all-ready      # 모든 Ready 태스크 프롬프트 생성
```

### 코드 리뷰 & 검수
```bash
./tmh.py generate-scripts      # 각 워크트리에 run_claude.sh 생성
./tmh.py generate-review [ids] # Git diff 기반 리뷰 요청 생성
./tmh.py auto-review [ids]     # 리뷰 생성 + Opus 자동 전송
```

### 검증 & 디버깅
```bash
./tmh.py verify-kickoff [ids]  # 킥오프 설정 검증
./tmh.py claude-ready          # Claude CLI 대화형 실행
```

## 🔧 설정 옵션

환경변수로 기본 설정을 변경할 수 있습니다:

```bash
export WORKTREE_BASE="../workspace"  # 워크트리 기본 경로 (기본: ../ws)
export BRANCH_PREFIX="feature/"      # 브랜치 접두사 (기본: ws/)
export TMH_AUTO_REVIEW="true"        # 자동 Opus 리뷰 활성화
```

## 📁 프로젝트 구조

TMH 실행 후 생성되는 파일들:

```
your-project/
├── tmh.py                    # TMH 스크립트
├── prompts/                  # 생성된 프롬프트 파일들
│   ├── 3.txt
│   ├── 6.txt
│   └── 7.txt
├── reviews/                  # 코드 리뷰 요청 파일들
│   ├── task_3_review.md
│   ├── task_6_review.md
│   └── task_7_review.md
└── ../ws/                    # 워크트리들 (프로젝트 외부)
    ├── 3-task-name/
    │   └── run_claude.sh     # Claude CLI 실행 스크립트
    ├── 6-task-name/
    └── 7-task-name/
```

## 🎯 워크플로우 예시

### 전형적인 병렬 개발 세션

```bash
# 1. 현재 상황 파악
./tmh.py debug-ready
# Output: Ready tasks: 3, 6, 7

# 2. 병렬 작업 환경 구성
./tmh.py kickoff-ready-claude
# → 3개의 워크트리 생성
# → VS Code 3개 창 열림
# → 각각에서 Claude CLI 자동 실행 시도

# 3. 각 워크트리에서 작업 (수동)
cd ../ws/3-realtime-core-mvp && ./run_claude.sh
cd ../ws/6-monitoring-dashboard && ./run_claude.sh  
cd ../ws/7-ui-skeleton && ./run_claude.sh

# 4. 작업 완료 후 리뷰
./tmh.py generate-review 3,6,7

# 5. 메인에서 Opus 검수
cat reviews/task_3_review.md | claude --dangerously-skip-permissions
cat reviews/task_6_review.md | claude --dangerously-skip-permissions
cat reviews/task_7_review.md | claude --dangerously-skip-permissions

# 6. 승인된 작업들 메인에 머지
git checkout main
git merge ws/3-realtime-core-mvp
git merge ws/6-monitoring-dashboard  
git merge ws/7-ui-skeleton
```

## 🔍 트러블슈팅

### 일반적인 문제들

**Q: "No ready tasks found"**
```bash
# 태스크 상태 확인
tm list --tag your-tag

# 의존성 문제 해결
tm validate-dependencies
tm fix-dependencies
```

**Q: "Claude CLI not found"**
```bash
# Claude CLI 설치 확인
which claude
claude --version

# 토큰 재설정
claude setup-token
```

**Q: "Git worktree 생성 실패"**
```bash
# 초기 커밋 필요
git add . && git commit -m "Initial commit"

# 기존 워크트리 정리
git worktree prune
```

**Q: "jq command not found"**
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# 다른 방법들
# https://stedolan.github.io/jq/download/
```

## 🤝 기여하기

버그 리포트, 기능 요청, PR 모두 환영합니다!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 라이선스

MIT License - 자유롭게 사용하세요!

## 🙏 감사 인사

- [Task Master AI](https://github.com/eyal-taskmaster/task-master-ai) - 핵심 태스크 관리 시스템
- [Claude CLI](https://docs.claude.ai/claude-code) - AI 코딩 어시스턴트
- Git Worktree - 병렬 개발 환경 제공

---

**Happy Parallel Coding! 🚀** 