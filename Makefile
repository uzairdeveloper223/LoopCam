PREFIX ?= /usr
APPNAME = loopcam
APPDIR = $(PREFIX)/share/$(APPNAME)
BINDIR = $(PREFIX)/bin
DATADIR = $(PREFIX)/share/applications
ICONDIR = $(PREFIX)/share/icons/hicolor/scalable/apps
METAINFO = $(PREFIX)/share/metainfo

.PHONY: all install uninstall clean

all:
	@echo "python requires no compilation. build complete."

install:
	install -d $(DESTDIR)$(APPDIR)
	install -m 755 loopcam.py $(DESTDIR)$(APPDIR)/$(APPNAME)
	install -d $(DESTDIR)$(BINDIR)
	ln -sf $(APPDIR)/$(APPNAME) $(DESTDIR)$(BINDIR)/$(APPNAME)
	install -d $(DESTDIR)$(DATADIR)
	install -m 644 data/com.github.uzairdeveloper223.loopcam.desktop $(DESTDIR)$(DATADIR)/$(APPNAME).desktop
	install -d $(DESTDIR)$(ICONDIR)
	install -m 644 data/loopcam.svg $(DESTDIR)$(ICONDIR)/$(APPNAME).svg
	install -d $(DESTDIR)$(METAINFO)
	install -m 644 data/com.github.uzairdeveloper223.loopcam.metainfo.xml $(DESTDIR)$(METAINFO)/$(APPNAME).metainfo.xml

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/$(APPNAME)
	rm -rf $(DESTDIR)$(APPDIR)
	rm -f $(DESTDIR)$(DATADIR)/$(APPNAME).desktop
	rm -f $(DESTDIR)$(ICONDIR)/$(APPNAME).svg
	rm -f $(DESTDIR)$(METAINFO)/$(APPNAME).metainfo.xml

clean:
	@echo "nothing to clean."
