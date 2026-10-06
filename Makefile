.PHONY: up down seed eval test api web

up:
	docker compose up --build

down:
	docker compose down

seed:
	python scripts/seed_demo.py payment-latency-spike

eval:
	python evals/run_eval.py

test:
	pytest tests -q

api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev
