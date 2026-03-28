# Makefile for PRD Enforcement
# Multi-Agent EM Roadmap Platform

.PHONY: prd-check prd-validate prd-status prd-update-check help

# Default target
help:
	@echo "PRD Enforcement Commands:"
	@echo "  make prd-check      - Quick PRD health check"
	@echo "  make prd-validate   - Full PRD validation"
	@echo "  make prd-status     - Current PRD status report"
	@echo "  make prd-update-check - Check if PRD needs updates"
	@echo ""
	@echo "Usage examples:"
	@echo "  make prd-check                    # Quick health check"
	@echo "  make prd-validate                  # Full validation"
	@echo "  make prd-update-check              # Check what needs updating"

# Quick PRD health check
prd-check:
	@echo "🔍 Quick PRD Health Check..."
	@echo "=========================="
	@if [ ! -f "PRD.md" ]; then \
		echo "❌ PRD.md not found!"; \
		exit 1; \
	fi
	@echo "✅ PRD.md exists"
	@grep -q "Version:" PRD.md && echo "✅ Version field present" || echo "❌ Version field missing"
	@grep -q "Change Log" PRD.md && echo "✅ Change Log present" || echo "❌ Change Log missing"
	@grep -q "Roadmap" PRD.md && echo "✅ Roadmap present" || echo "❌ Roadmap missing"
	@echo "=========================="
	@echo "Run 'make prd-validate' for full validation"

# Full PRD validation
prd-validate:
	@echo "🔍 Full PRD Validation..."
	@echo "=========================="
	@python3 .windsurf/scripts/prd_validator.py
	@echo "=========================="

# Current PRD status
prd-status:
	@echo "📊 Current PRD Status"
	@echo "===================="
	@if [ -f "PRD.md" ]; then \
		echo "📄 PRD Version: $$(grep 'Version:' PRD.md | sed 's/.*Version: *//')"; \
		echo "📅 Last Updated: $$(grep 'Last Updated:' PRD.md | sed 's/.*Last Updated: *//')"; \
		echo "📝 Change Log Entries: $$(grep -c '^[|].*[|].*[|].*[|]' PRD.md)"; \
		echo "✅ Completed Items: $$(grep -c '\- \[x\]' PRD.md)"; \
		echo "⏳ Pending Items: $$(grep -c '\- \[ \]' PRD.md)"; \
	else \
		echo "❌ PRD.md not found!"; \
	fi
	@echo "===================="

# Check if PRD needs updates based on recent changes
prd-update-check:
	@echo "🔍 Checking if PRD needs updates..."
	@echo "================================="
	@echo "Recent changes in last 24 hours:"
	@find . -name "*.py" -mtime -1 2>/dev/null | head -5 || echo "No recent Python changes"
	@echo ""
	@echo "Files changed in last commit:"
	@git diff --name-only HEAD~1 HEAD 2>/dev/null | head -5 || echo "No git history available"
	@echo ""
	@echo "💡 Consider running PRD validation if you made significant changes:"
	@echo "   make prd-validate"
	@echo "================================="

# Pre-commit hook check
pre-commit-check:
	@echo "🔍 Pre-commit PRD Check..."
	@echo "=========================="
	@python3 .windsurf/scripts/prd_validator.py
	@if [ $$? -eq 0 ]; then \
		echo "✅ PRD validation passed - commit allowed"; \
	else \
		echo "❌ PRD validation failed - please update PRD before committing"; \
		exit 1; \
	fi

# Install pre-commit hook (optional)
install-pre-commit:
	@echo "🔧 Installing pre-commit hook..."
	@mkdir -p .git/hooks
	@echo '#!/bin/sh' > .git/hooks/pre-commit
	@echo '# Pre-commit PRD validation hook' >> .git/hooks/pre-commit
	@echo 'make pre-commit-check' >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Pre-commit hook installed"
	@echo "⚠️  This will enforce PRD validation before every commit"

# Remove pre-commit hook
remove-pre-commit:
	@echo "🗑️  Removing pre-commit hook..."
	@rm -f .git/hooks/pre-commit
	@echo "✅ Pre-commit hook removed"

# Create PRD status report
prd-report:
	@echo "📋 PRD Status Report"
	@echo "==================="
	@echo "Generated: $$(date)"
	@echo ""
	@if [ -f "PRD.md" ]; then \
		echo "## PRD Information"; \
		echo "Version: $$(grep 'Version:' PRD.md | sed 's/.*Version: *//')"; \
		echo "Last Updated: $$(grep 'Last Updated:' PRD.md | sed 's/.*Last Updated: *//')"; \
		echo "Status: $$(grep 'Status:' PRD.md | sed 's/.*Status: *//')"; \
		echo ""; \
		echo "## Content Summary"; \
		echo "Total Lines: $$(wc -l < PRD.md)"; \
		echo "Change Log Entries: $$(grep -c '^[|].*[|].*[|].*[|]' PRD.md)"; \
		echo "Completed Items: $$(grep -c '\- \[x\]' PRD.md)"; \
		echo "Pending Items: $$(grep -c '\- \[ \]' PRD.md)"; \
		echo ""; \
		echo "## Validation Status"; \
		python3 .windsurf/scripts/prd_validator.py >/dev/null 2>&1 && echo "✅ Validation PASSED" || echo "❌ Validation FAILED"; \
	else \
		echo "❌ PRD.md not found!"; \
	fi
	@echo "==================="
