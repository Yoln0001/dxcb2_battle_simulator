"""Uvicorn启动配置；从项目根目录server.py进入。"""
import argparse
from pathlib import Path

import uvicorn

def main():
    parser = argparse.ArgumentParser(description='FastAPI技能接口与配置页面')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--reload', action=argparse.BooleanOptionalAction, default=True, help='修改后端代码后自动重启（默认开启，--no-reload可关闭）')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须为1～65535')
    print(f'页面：http://127.0.0.1:{args.port}/', flush=True)
    print(f'接口文档：http://127.0.0.1:{args.port}/docs', flush=True)
    uvicorn.run('backend.app:create_app', factory=True, host='127.0.0.1', port=args.port,
                reload=args.reload, reload_dirs=[str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'engine')] if args.reload else None)

if __name__ == '__main__':
    main()
