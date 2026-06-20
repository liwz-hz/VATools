#!/bin/bash

# VATools 一键启动脚本
# 用途：启动后端 Flask 服务和前端 React 开发服务器

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 日志文件
LOG_DIR="$PROJECT_ROOT/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# PID 文件
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    print_info "检查系统依赖..."
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        print_error "未找到 Python 3，请先安装 Python 3.9+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    print_success "Python 3 已安装: $(python3 --version)"
    
    # 检查 Python 版本兼容性
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -gt 11 ]; then
        print_warning "检测到 Python $PYTHON_VERSION"
        print_warning "音源分离功能需要 Python 3.9-3.11"
        print_info "其他功能（音频提取、编辑）可正常使用"
    fi
    
    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        print_error "未找到 Node.js，请先安装 Node.js 18+"
        exit 1
    fi
    print_success "Node.js 已安装: $(node --version)"
    
    # 检查 FFmpeg
    if ! command -v ffmpeg &> /dev/null; then
        print_warning "未找到 FFmpeg，音频处理功能将不可用"
        print_info "安装方法: brew install ffmpeg (macOS)"
    else
        print_success "FFmpeg 已安装: $(ffmpeg -version | head -n1)"
    fi
}

# 安装后端依赖
install_backend_deps() {
    print_info "检查后端依赖..."
    
    cd "$BACKEND_DIR"
    
    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        print_info "创建 Python 虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 安装依赖
    if [ ! -f "venv/lib/python*/site-packages/flask/__init__.py" ]; then
        print_info "安装后端 Python 依赖..."
        pip install -r requirements.txt
    else
        print_success "后端依赖已安装"
    fi
    
    cd "$PROJECT_ROOT"
}

# 安装前端依赖
install_frontend_deps() {
    print_info "检查前端依赖..."
    
    cd "$FRONTEND_DIR"
    
    # 检查 node_modules
    if [ ! -d "node_modules" ]; then
        print_info "安装前端 Node.js 依赖..."
        npm install
    else
        print_success "前端依赖已安装"
    fi
    
    cd "$PROJECT_ROOT"
}

# 创建必要的目录
create_directories() {
    print_info "创建必要的目录..."
    
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKEND_DIR/uploads"
    mkdir -p "$BACKEND_DIR/workspace/audio"
    mkdir -p "$BACKEND_DIR/workspace/separated"
    mkdir -p "$BACKEND_DIR/workspace/edited"
    mkdir -p "$BACKEND_DIR/logs"
    
    print_success "目录创建完成"
}

# 启动后端服务
start_backend() {
    print_info "启动后端服务..."
    
    # 清理占用端口的进程
    if lsof -ti:5001 > /dev/null 2>&1; then
        print_warning "端口 5001 被占用，正在清理..."
        lsof -ti:5001 | xargs kill -9 2>/dev/null
        sleep 1
    fi
    
    cd "$BACKEND_DIR"
    source venv/bin/activate
    
    # 检查是否已在运行
    if [ -f "$BACKEND_PID_FILE" ]; then
        PID=$(cat "$BACKEND_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_warning "后端服务已在运行 (PID: $PID)"
            return
        fi
    fi
    
    # 启动后端
    nohup python run.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$BACKEND_PID_FILE"
    
    # 等待启动
    sleep 2
    
    # 检查是否启动成功
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        print_success "后端服务已启动 (PID: $BACKEND_PID)"
        print_info "后端地址: http://localhost:5001"
        print_info "后端日志: $BACKEND_LOG"
    else
        print_error "后端服务启动失败，请查看日志: $BACKEND_LOG"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
}

# 启动前端服务
start_frontend() {
    print_info "启动前端服务..."
    
    # 清理占用端口的进程
    if lsof -ti:3000 > /dev/null 2>&1; then
        print_warning "端口 3000 被占用，正在清理..."
        lsof -ti:3000 | xargs kill -9 2>/dev/null
        sleep 1
    fi
    
    cd "$FRONTEND_DIR"
    
    # 检查是否已在运行
    if [ -f "$FRONTEND_PID_FILE" ]; then
        PID=$(cat "$FRONTEND_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_warning "前端服务已在运行 (PID: $PID)"
            return
        fi
    fi
    
    # 启动前端
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
    
    # 等待启动
    sleep 3
    
    # 检查是否启动成功
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        print_success "前端服务已启动 (PID: $FRONTEND_PID)"
        print_info "前端地址: http://localhost:3000"
        print_info "前端日志: $FRONTEND_LOG"
    else
        print_error "前端服务启动失败，请查看日志: $FRONTEND_LOG"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
}

# 停止服务
stop_services() {
    print_info "停止服务..."
    
    # 停止后端
    if [ -f "$BACKEND_PID_FILE" ]; then
        PID=$(cat "$BACKEND_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            print_success "后端服务已停止 (PID: $PID)"
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    
    # 停止前端
    if [ -f "$FRONTEND_PID_FILE" ]; then
        PID=$(cat "$FRONTEND_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            print_success "前端服务已停止 (PID: $PID)"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi
    
    print_success "所有服务已停止"
}

# 查看服务状态
status_services() {
    print_info "服务状态:"
    
    # 后端状态
    if [ -f "$BACKEND_PID_FILE" ]; then
        PID=$(cat "$BACKEND_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_success "后端服务运行中 (PID: $PID) - http://localhost:5001"
        else
            print_warning "后端服务已停止"
        fi
    else
        print_info "后端服务未启动"
    fi
    
    # 前端状态
    if [ -f "$FRONTEND_PID_FILE" ]; then
        PID=$(cat "$FRONTEND_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_success "前端服务运行中 (PID: $PID) - http://localhost:3000"
        else
            print_warning "前端服务已停止"
        fi
    else
        print_info "前端服务未启动"
    fi
}

# 查看日志
view_logs() {
    print_info "查看日志 (按 Ctrl+C 退出)..."
    
    if [ -f "$BACKEND_LOG" ] && [ -f "$FRONTEND_LOG" ]; then
        tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
    elif [ -f "$BACKEND_LOG" ]; then
        tail -f "$BACKEND_LOG"
    elif [ -f "$FRONTEND_LOG" ]; then
        tail -f "$FRONTEND_LOG"
    else
        print_warning "没有找到日志文件"
    fi
}

# 显示帮助
show_help() {
    echo "VATools 一键启动脚本"
    echo ""
    echo "用法: ./start.sh [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动所有服务 (默认)"
    echo "  stop      停止所有服务"
    echo "  restart   重启所有服务"
    echo "  status    查看服务状态"
    echo "  logs      查看日志"
    echo "  install   安装所有依赖"
    echo "  help      显示帮助信息"
    echo ""
    echo "示例:"
    echo "  ./start.sh           # 启动所有服务"
    echo "  ./start.sh start     # 启动所有服务"
    echo "  ./start.sh stop      # 停止所有服务"
    echo "  ./start.sh status    # 查看服务状态"
    echo "  ./start.sh logs      # 查看日志"
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            print_info "=== VATools 启动脚本 ==="
            check_dependencies
            create_directories
            install_backend_deps
            install_frontend_deps
            start_backend
            start_frontend
            print_success "=== 所有服务已启动 ==="
            echo ""
            print_info "访问地址:"
            echo "  前端: http://localhost:3000"
            echo "  后端: http://localhost:5001"
            echo ""
            print_info "管理命令:"
            echo "  停止服务: ./start.sh stop"
            echo "  查看状态: ./start.sh status"
            echo "  查看日志: ./start.sh logs"
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            sleep 1
            print_info "=== 重启服务 ==="
            start_backend
            start_frontend
            print_success "=== 服务已重启 ==="
            ;;
        status)
            status_services
            ;;
        logs)
            view_logs
            ;;
        install)
            check_dependencies
            install_backend_deps
            install_frontend_deps
            print_success "所有依赖已安装"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
