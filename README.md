# 伟大作品™️工作室 ChatFLOW 2.1.3

本地外贸建站工具：产品、板块、页面、多语言、SEO / AI GEO、预览、备份和 GitHub Pages 发布。

用户说明见 [RELEASE_GUIDE.md](RELEASE_GUIDE.md)，本版变化见 [RELEASE_NOTES.md](RELEASE_NOTES.md)。

开发：Python 3.12，`python -m pip install -r requirements.txt`，`python app.py`。
测试：`python -m unittest discover -s tests -v`。测试使用临时数据，不连接实际账号。
打包：`python -m PyInstaller chatflow.spec --noconfirm`。冻结程序自检：`python scripts/smoke_bundle.py`。

GitHub Actions 手动启动 build-release，分别构建 Windows x64、macOS Intel、Apple Silicon；源代码检查与冻结程序自检通过后创建草稿 Release，验收后再发布。

程序资源与用户数据分离；升级复用原数据目录。CF_DATA_DIR 可指定独立数据目录用于测试。安装包只包含程序和公开的授权服务地址，不包含客户数据库、激活记录或开发者 Token。

2.1.2 新增推广工具箱、公开商品采集、关键词和店铺链接发现、多 SKU 草稿、本地 AI 翻译。使用本地 Qwen3-4B-Instruct-2507，首次下载约 2.5GB 模型及运行引擎，之后在本机翻译，不需要云端 API 账号。建议 8GB 以上内存并预留 6GB 磁盘。原文语言可自动识别或手动指定。本地 AI 生成的是待校对译稿，实测部分语言可能译错材质、颜色，导入和发布前请核对，不保证达到人工翻译标准。具体可用范围与操作入口见使用说明。

模型来源：[Qwen3-4B-Instruct-2507 原版](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)（Apache 2.0），使用社区 [Unsloth 固定版本的 Q4_K_M 转换](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/tree/a06e946bb6b655725eafa393f4a9745d460374c9)，它不是 Qwen 官方发布的 GGUF。下载时核对 SHA-256。运行引擎为官方 [llama.cpp b10894](https://github.com/ggml-org/llama.cpp/tree/b10894)（MIT），简繁转换使用 [OpenCC](https://github.com/BYVoid/OpenCC)（Apache 2.0）。
