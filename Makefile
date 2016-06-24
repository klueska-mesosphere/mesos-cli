EXEC = mesos
PLUGIN_PATH = lib/mesos/plugins
PLUGINS := $(shell find $(PLUGIN_PATH) -mindepth 1 -maxdepth 1 -type d)
PLUGINS := $(notdir $(PLUGINS))

SPECPATH=.virtualenv
DISTPATH=$(SPECPATH)/bin
WORKPATH=$(SPECPATH)/build

HIDDEN_IMPORTS = $(patsubst %, --hidden-import mesos.plugins.%, $(PLUGINS))

$(EXEC):
	@pyinstaller --paths=$(PWD)/lib \
	             --specpath $(SPECPATH) \
	             --distpath $(DISTPATH) \
	             --workpath $(WORKPATH) \
	             $(HIDDEN_IMPORTS) \
	             --onefile bin/$(EXEC)

clean:
	find . -name "*.pyc" | xargs rm -rf
	rm -rf $(SPECPATH)/*.spec $(WORKPATH) $(DISTPATH)/$(EXEC)
