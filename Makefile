ifndef CHARM_BUILD_DIR
    CHARM_BUILD_DIR := $(shell pwd)/builds
    $(warning Warning CHARM_BUILD_DIR was not set, defaulting to $(CHARM_BUILD_DIR))
endif

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make lint - run flake8"
	@echo " make test - run the unittests and lint"
	@echo " make unittest - run the tests defined in the unittest subdirectory"
	@echo " make functional - run the tests defined in the functional subdirectory"
	@echo " make release - build the charm"
	@echo " make clean - remove unneeded files"
	@echo ""

lint:
	@echo "Running flake8"
	@cd src && tox -e lint

test: unittest functional lint

unittest:
	@cd src && tox -e unit

functional: build
	@cd src && tox -e functional

build:
	@echo "Building charm to base directory $(CHARM_BUILD_DIR)"
	@CHARM_LAYERS_DIR=./layers CHARM_INTERFACES_DIR=./interfaces TERM=linux\
		CHARM_BUILD_DIR=$(CHARM_BUILD_DIR) charm build ./src --force

release: clean build
	@echo "Charm is built at $(CHARM_BUILD_DIR)"

clean:
	@echo "Cleaning files"
	@if [ -d src/.tox ] ; then rm -r src/.tox ; fi
	@if [ -d src/.pytest_cache ] ; then rm -r src/.pytest_cache ; fi

# The targets below don't depend on a file
.PHONY: lint test unittest functional build release clean help
