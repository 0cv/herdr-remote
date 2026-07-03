ifneq (,$(wildcard .env))
include .env
export
endif

WEB_PROJECT ?= herdr-remote
PATH := /opt/homebrew/bin:/usr/local/bin:/home/linuxbrew/.linuxbrew/bin:$(HOME)/.local/bin:$(PATH)
export PATH

.PHONY: help relay-install relay-run relay-plugin service-install service-uninstall service-status service-logs linux-service-install linux-service-uninstall linux-service-status linux-service-logs web-deploy web-preview mac-build ios-build

help:
	@echo "Common targets:"
	@echo "  make web-deploy       Deploy ./web to Cloudflare Pages (WEB_PROJECT=$(WEB_PROJECT))"
	@echo "  make service-install  Install/start macOS launchd relay+tunnel service"
	@echo "  make service-status   Show launchd service status"
	@echo "  make service-logs     Tail relay+tunnel service logs"
	@echo "  make service-uninstall Stop/remove launchd service"
	@echo "  make linux-service-install  Install/start systemd user relay+tunnel service"
	@echo "  make linux-service-status   Show systemd user service status"
	@echo "  make linux-service-logs     Tail systemd user service logs"
	@echo "  make linux-service-uninstall Stop/remove systemd user service"
	@echo "  make relay-run        Run relay in the foreground"

relay-install:
	@echo "No separate install step: relay scripts declare uv dependencies inline."

relay-run:
	uv run relay/herdr_relay.py

relay-plugin:
	herdr plugin link relay/

service-install:
	relay/install-service.sh

service-uninstall:
	relay/uninstall-service.sh

service-status:
	launchctl print gui/$$(id -u)/com.herdr-remote.service

service-logs:
	tail -f "$$HOME/Library/Logs/herdr-remote/service.log" "$$HOME/Library/Logs/herdr-remote/service.err"

linux-service-install:
	relay/install-systemd-user-service.sh

linux-service-uninstall:
	relay/uninstall-systemd-user-service.sh

linux-service-status:
	systemctl --user status herdr-remote.service

linux-service-logs:
	journalctl --user -u herdr-remote.service -f

web-deploy:
	npx wrangler pages deploy web --project-name "$(WEB_PROJECT)"

web-preview:
	npx wrangler pages dev web

mac-build:
	cd herdi-mac && swift build

ios-build:
	xcodebuild -project herdi-ios/Herdi.xcodeproj -scheme Herdi -destination 'generic/platform=iOS' build
