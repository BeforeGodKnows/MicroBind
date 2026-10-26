.PHONY: install test scan demo
install:
	python -m pip install -e '.[test]'
test:
	python -m pytest -q
scan:
	python -m microbind scan demo/project.yml --out out/scan
demo:
	python -m microbind demo --out out/demo
