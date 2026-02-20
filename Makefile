GRAPHICS ?= false
SWAP_COLUMNS ?= false
GRAPHICS_FLAG = $(if $(filter true,$(GRAPHICS)),--graphics,)
COLUMNS_FLAG = $(if $(filter true,$(SWAP_COLUMNS)),--swap-columns,)
PROFILE ?= default
SOURCE_DIR=resume_cli
TESTS_PATH=tests

# Default to running unit tests
MARK ?=

.PHONY: test unit-test function-test test-all help
.PHONY: install pylint black flake8 ruff checkin pre-commit
.PHONY: all render $(TEMPLATES) clean

# Detect all template directories
TEMPLATES := $(notdir $(wildcard templates/*))

all: $(TEMPLATES)

$(TEMPLATES):
	@echo "--- Rendering Resume ---"
	@poetry run python main.py \
		--templatefile templates/$@/resume.tex.j2 \
		--profile profiles/$@/$(PROFILE).yaml \
		--output templates/$@/resume.tex \
		$(GRAPHICS_FLAG) $(COLUMNS_FLAG) \
		jobdescriptions/job1.txt

	@if [ -f templates/$@/cover_letter.tex.j2 ]; then \
		echo "--- Rendering Cover Letter ---"; \
		poetry run python main.py \
			--templatefile templates/$@/cover_letter.tex.j2 \
			--profile profiles/$@/$(PROFILE).yaml \
			--output templates/$@/cover_letter.tex \
			$(GRAPHICS_FLAG) \
			jobdescriptions/job1.txt; \
	fi
	# Now just call the sub-makefile to do the LaTeX work
	$(MAKE) -C templates/$@

clean:
	@find templates -name "*.aux" -delete
	@find templates -name "*.log" -delete
	@find templates -name "*.out" -delete
	@find templates -name "resume.tex" -delete
	@find templates -name "cover_letter.tex" -delete
	@find templates -name "*.pdf" -delete

# Variables
INPUT_JSON = resume.json
INPUT_YAML = resume.yaml
OUTPUT_JSON = converted.json
OUTPUT_YAML = converted.yaml

# Target to convert JSON to YAML
json_to_yaml:
	python3 -c 'import sys, yaml, json; print(yaml.dump(json.load(sys.stdin), default_flow_style=False))' < $(INPUT_JSON) > $(OUTPUT_YAML)

# Target to convert YAML to JSON
yaml_to_json:
	python3 -c 'import sys, yaml, json; print(json.dumps(yaml.safe_load(sys.stdin), indent=2))' < $(INPUT_YAML) > $(OUTPUT_JSON)

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Project Installation ---
install: ## Install project dependencies
	poetry install

# --- Linting & Formatting Targets (Matching linting.yml) ---
pylint: ## Lint code with pylint
	@echo "Linting code with pylint..."
	poetry run pylint --rcfile=.pylintrc $(SOURCE_DIR)/

black-check: ## Reformat code with black
	@echo "Reformatting code with black..."
	poetry run black --check .

flake8-check: ## Lint code with flake8
	@echo "Linting code with flake8..."
	poetry run flake8 $(SOURCE_DIR)/

ruff-check: ## Lint code with ruff
	@echo "Linting code with ruff..."
	poetry run ruff check .

isort-check: ## Lint code with isort
	@echo "Linting code with ruff..."
	poetry run isort check .

# --- Tests ---
test: ## Runs tests based on MARK.
	@echo "Running tests with filter: $(MARK)"
	@PYTHONPATH=. poetry run pytest \
		$(MARK) \
		-vv \
		-s \
		--cov=$(SOURCE_DIR) \
		$(TESTS_PATH) \
		--cov-report=term \
		--cov-report=html

unit-test: ## Alias for isolated unit tests
	@$(MAKE) test MARK="-m unit"

function-test: ## Alias for functional workflow tests
	@$(MAKE) test MARK="-m functional"

# --- Git / Utils ---
checkin: ## Git commit and push, allows for a dynamic comment
	@echo "Checking in changes..."
	@git status
	$(eval COMMENT := $(shell bash -c 'read -e -p "Comment: " var; echo $$var'))
	@git add --all; \
	 git commit --no-verify -m "$(COMMENT)"; \
	 git push

# Install pre-commit hooks into your .git/ directory
install-hooks:
	poetry run pre-commit install

# Run all hooks manually on all files
pre-commit:
	poetry run pre-commit run --all-files

test-pip-install:
	@echo "Installing from testpypi..."
	pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ resume-cli