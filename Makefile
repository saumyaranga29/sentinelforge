.PHONY: help install test eval lint check run docker-build docker-run

help:
	@echo "SentinelForge Developer Commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make test         - Run 25+ automated unit and security tests"
	@echo "  make eval         - Run in-repository RAG retrieval benchmark"
	@echo "  make check        - Run full automated check suite (tests + benchmark)"
	@echo "  make run          - Start SentinelForge API server"
	@echo "  make docker-build - Build Docker container"
	@echo "  make docker-run   - Run application inside Docker container"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

eval:
	python eval/run_eval.py

check: test eval

run:
	uvicorn sentinelforge.api.app:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t sentinelforge:latest -f docker/Dockerfile .

docker-run:
	docker run -p 8000:8000 sentinelforge:latest

