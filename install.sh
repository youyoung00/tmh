#!/bin/bash

# TMH (Task Master Helper) 설치 스크립트
# Usage: curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/tmh/main/install.sh | bash

set -e

echo "🚀 TMH (Task Master Helper) 설치를 시작합니다..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수들
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 필수 도구 확인
check_requirements() {
    echo ""
    echo "🔍 필수 도구들을 확인합니다..."
    
    local missing_tools=()
    
    # Git 확인
    if ! command -v git &> /dev/null; then
        missing_tools+=("git")
    else
        print_success "Git $(git --version | cut -d' ' -f3)"
    fi
    
    # jq 확인
    if ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
    else
        print_success "jq $(jq --version)"
    fi
    
    # Task Master AI 확인
    if ! command -v tm &> /dev/null; then
        missing_tools+=("task-master-ai")
    else
        print_success "Task Master AI installed"
    fi
    
    # Claude CLI 확인
    if ! command -v claude &> /dev/null; then
        missing_tools+=("claude")
    else
        print_success "Claude CLI installed"
    fi
    
    # 누락된 도구들 처리
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo ""
        print_error "다음 도구들이 설치되지 않았습니다:"
        for tool in "${missing_tools[@]}"; do
            echo "  - $tool"
        done
        echo ""
        print_info "설치 방법:"
        
        if [[ " ${missing_tools[*]} " =~ " jq " ]]; then
            echo "  jq: brew install jq (macOS) 또는 apt-get install jq (Ubuntu)"
        fi
        
        if [[ " ${missing_tools[*]} " =~ " task-master-ai " ]]; then
            echo "  Task Master AI: npm install -g task-master-ai"
        fi
        
        if [[ " ${missing_tools[*]} " =~ " claude " ]]; then
            echo "  Claude CLI: https://docs.claude.ai/claude-code"
        fi
        
        echo ""
        read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "설치가 중단되었습니다."
            exit 1
        fi
    fi
}

# TMH 다운로드
download_tmh() {
    echo ""
    echo "📥 TMH 스크립트를 다운로드합니다..."
    
    if command -v curl &> /dev/null; then
        curl -sSL https://raw.githubusercontent.com/youyoung00/tmh/main/tmh.py -o tmh.py
    elif command -v wget &> /dev/null; then
        wget -q https://raw.githubusercontent.com/youyoung00/tmh/main/tmh.py -O tmh.py
    else
        print_error "curl 또는 wget이 필요합니다."
        exit 1
    fi
    
    chmod +x tmh.py
    print_success "tmh.py 다운로드 완료"
}

# 설정 확인
check_setup() {
    echo ""
    echo "🔧 기본 설정을 확인합니다..."
    
    # Claude CLI 토큰 확인
    if ! claude --version &> /dev/null; then
        print_warning "Claude CLI 토큰이 설정되지 않았을 수 있습니다."
        echo "  다음 명령어로 토큰을 설정하세요: claude setup-token"
    else
        print_success "Claude CLI 설정 확인됨"
    fi
    
    # Git 설정 확인
    if ! git config --get user.name &> /dev/null || ! git config --get user.email &> /dev/null; then
        print_warning "Git 사용자 정보가 설정되지 않았습니다."
        echo "  다음 명령어들로 설정하세요:"
        echo "    git config --global user.name \"Your Name\""
        echo "    git config --global user.email \"your@email.com\""
    else
        print_success "Git 사용자 정보 설정 확인됨"
    fi
}

# 사용법 안내
show_usage() {
    echo ""
    echo "🎉 TMH 설치가 완료되었습니다!"
    echo ""
    echo "📋 빠른 시작 가이드:"
    echo ""
    echo "1. Task Master 프로젝트 초기화:"
    echo "   tm init"
    echo ""
    echo "2. Ready 태스크 확인:"
    echo "   ./tmh.py debug-ready"
    echo ""
    echo "3. 병렬 작업 시작:"
    echo "   ./tmh.py kickoff-ready-claude"
    echo ""
    echo "4. 코드 리뷰 생성:"
    echo "   ./tmh.py generate-review [task_ids]"
    echo ""
    echo "📚 전체 문서: https://github.com/youyoung00/tmh"
    echo ""
    print_success "Happy Parallel Coding! 🚀"
}

# 메인 실행
main() {
    check_requirements
    download_tmh
    check_setup
    show_usage
}

# 스크립트 실행
main "$@" 