PROJECTPATH = $(dir $(realpath $(MAKEFILE_LIST)))
LAYERS_DIR = $(PROJECTPATH)/layers
INTERFACES_DIR = $(PROJECTPATH)/interfaces

ifndef CHARM_BUILD_DIR
    CHARM_BUILD_DIR := $(PROJECTPATH)
    $(warning Warning CHARM_BUILD_DIR was not set, defaulting to $(CHARM_BUILD_DIR))
endif

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make lint - run flake8"
	@echo " make test - run the unittests and lint"
	@echo " make unittest - run the tests defined in the unittest subdirectory"
	@echo " make release - build the charm"
	@echo " make clean - remove unneeded files"
	@echo ""

lint:
	@echo "Running flake8"
	@cd src && tox -e lint

test: unittest lint

unittest:
	@cd src && tox -e unit

build:
	@echo "Building charm to base directory $(CHARM_BUILD_DIR)"
	@CHARM_LAYERS_DIR=$(LAYERS_DIR) CHARM_INTERFACES_DIR=$(INTERFACES_DIR) TERM=linux\
		charm build --output-dir $(CHARM_BUILD_DIR) $(PROJECTPATH)/src --force

release: clean build
	@echo "Charm is built at $(CHARM_BUILD_DIR)"

clean:
	@echo "Cleaning files"
	@if [ -d $(CHARM_BUILD_DIR)/builds ] ; then rm -r $(CHARM_BUILD_DIR)/builds ; fi
	@if [ -d $(PROJECTPATH)/src/.tox ] ; then rm -r $(PROJECTPATH)/src/.tox ; fi
	@if [ -d $(PROJECTPATH)/src/.pytest_cache ] ; then rm -r $(PROJECTPATH)/src/.pytest_cache ; fi

# The targets below don't depend on a file
.PHONY: lint test unittest build release clean help
