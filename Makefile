# The hook every Python program a scenario runs loads, measured where it runs:
# it loads as sitecustomize, not as part of the pubtest package.
FUNCTIONAL_ENV = PUBTEST_CHILD_DIR=$(CURDIR)/src/pubtest/_child

include pubrules-python.mk

.PHONY: check

check: sync-check functional ## Everything CI runs
