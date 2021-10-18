PYTHON := /usr/bin/python3

PROJECTPATH=$(dir $(realpath $(MAKEFILE_LIST)))
ifndef CHARM_BUILD_DIR
	CHARM_BUILD_DIR=${PROJECTPATH}.build
endif
ifndef CHARM_LAYERS_DIR
	CHARM_LAYERS_DIR=${PROJECTPATH}/layers
endif
ifndef CHARM_INTERFACES_DIR
	CHARM_INTERFACES_DIR=${PROJECTPATH}/interfaces
endif
METADATA_FILE="src/metadata.yaml"
CHARM_NAME=$(shell cat ${PROJECTPATH}/${METADATA_FILE} | grep -E "^name:" | awk '{print $$2}')

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make clean - remove unneeded files"
	@echo " make submodules - make sure that the submodules are up-to-date"
	@echo " make submodules-update - update submodules to latest changes on remote branch"
	@echo " make build - build the charm"
	@echo " make release - run clean, submodules, and build targets"
	@echo " make lint - run flake8 and black --check"
	@echo " make reformat - run black and isort and reformat files"
	@echo " make proof - run charm proof"
	@echo " make unittests - run the tests defined in the unittest subdirectory"
	@echo " make functional - run the tests defined in the functional subdirectory"
	@echo " make test - run lint, proof, unittests and functional targets"
	@echo ""

clean:
	@echo "Cleaning files"
	@git clean -ffXd -e '!.idea'
	@echo "Cleaning existing build"
	@rm -rf ${CHARM_BUILD_DIR}/${CHARM_NAME}

submodules:
	# @echo "Cloning submodules"
	# @git submodule update --init --recursive
	@echo "No submodules. Skipping"

submodules-update:
	# @echo "Pulling latest updates for submodules"
	# @git submodule update --init --recursive --remote --merge
	@echo "No submodules. Skipping"

build:
	@echo "Building charm to directory ${CHARM_BUILD_DIR}/${CHARM_NAME}"
	@-git rev-parse --abbrev-ref HEAD > ./src/repo-info
	@CHARM_LAYERS_DIR=${CHARM_LAYERS_DIR} CHARM_INTERFACES_DIR=${CHARM_INTERFACES_DIR} \
		TERM=linux CHARM_BUILD_DIR=${CHARM_BUILD_DIR} charm build src/

release: clean build
	@echo "Charm is built at ${CHARM_BUILD_DIR}/${CHARM_NAME}"

lint:
	@echo "Running lint checks"
	@cd src && tox -e lint

reformat:
	@echo "Reformat files with black and isort"
	@cd src && tox -e reformat

proof: build
	@echo "Running charm proof"
	@charm proof ${CHARM_BUILD_DIR}/${CHARM_NAME}

unittests:
	@echo "Running unit tests"
	@cd src && tox -e unit

functional: build
	@echo "Executing functional tests in ${CHARM_BUILD_DIR}"
	@cd src && CHARM_BUILD_DIR=${CHARM_BUILD_DIR} tox -e func

test: lint proof unittests functional
	@echo "Tests completed for charm ${CHARM_NAME}."

pre-commit:
	@cd src && tox -e pre-commit

# The targets below don't depend on a file
.PHONY: help submodules submodules-update clean build release lint reformat proof unittests functional test
