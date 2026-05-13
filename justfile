set shell := ["powershell.exe", "-c"]

run:
    uv run src/main.py

fix:
    uvx ruff check --fix
    uvx ruff format

build:
    uv run pyinstaller --clean main.spec
