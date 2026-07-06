ifneq (,$(wildcard .env))
include .env
export
endif

WEB_PROJECT ?= herdr-mobile-relay
PATH := /opt/homebrew/bin:/usr/local/bin:/home/linuxbrew/.linuxbrew/bin:$(HOME)/.local/bin:$(PATH)
export PATH

.PHONY: help relay-install relay-run relay-plugin macos-service-install macos-service-uninstall macos-service-status macos-service-logs linux-service-install linux-service-uninstall linux-service-status linux-service-logs web-deploy web-preview

help:
	@echo "Common targets:"
	@echo "  make web-deploy                 Deploy ./web to Cloudflare Pages (WEB_PROJECT=$(WEB_PROJECT))"
	@echo "  make macos-service-install      Install/start macOS launchd relay+tunnel service"
	@echo "  make macos-service-status       Show macOS launchd service status"
	@echo "  make macos-service-logs         Tail macOS relay+tunnel service logs"
	@echo "  make macos-service-uninstall    Stop/remove macOS launchd service"
	@echo "  make linux-service-install      Install/start systemd user relay+tunnel service"
	@echo "  make linux-service-status       Show systemd user service status"
	@echo "  make linux-service-logs         Tail systemd user service logs"
	@echo "  make linux-service-uninstall    Stop/remove systemd user service"
	@echo "  make relay-run                  Run relay in the foreground"

relay-install:
	@echo "No separate install step: relay scripts declare uv dependencies inline."

relay-run:
	uv run relay/herdr_relay.py

relay-plugin:
	herdr plugin link relay/

macos-service-install:
	relay/install-service.sh

macos-service-uninstall:
	relay/uninstall-service.sh

macos-service-status:
	launchctl print gui/$$(id -u)/com.herdr-mobile-relay.service

macos-service-logs:
	tail -f "$$HOME/Library/Logs/herdr-mobile-relay/service.log" "$$HOME/Library/Logs/herdr-mobile-relay/service.err"

linux-service-install:
	relay/install-systemd-user-service.sh

linux-service-uninstall:
	relay/uninstall-systemd-user-service.sh

linux-service-status:
	systemctl --user status herdr-mobile-relay.service

linux-service-logs:
	journalctl --user -u herdr-mobile-relay.service -f

web-deploy:
	npx wrangler pages deploy web --project-name "$(WEB_PROJECT)"

web-preview:
	npx wrangler pages dev web
